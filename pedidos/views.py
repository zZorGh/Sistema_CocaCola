import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.db.models import Sum, F, Q, Count, ProtectedError, RestrictedError
from django.db import transaction
from django.core.paginator import Paginator
from django.core.cache import cache
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import logout as auth_logout
from .models import (Pedido, DetallePedido, Producto, Stock, Cliente, Pago, 
                     Transportista, OrdenDespacho, Devolucion, TicketSoporte, 
                     RegistroAuditoria, OrdenReabastecimiento)

# ==========================================
# RNF35 - SISTEMA DE SEGURIDAD POR ROLES
# ==========================================
def rol_requerido(*nombres_roles):
    def in_groups(user):
        if user.is_authenticated:
            if user.is_superuser or bool(user.groups.filter(name__in=nombres_roles)):
                return True
        return False
    return user_passes_test(in_groups, login_url='/')

# ==========================================
# CIERRE DE SESIÓN SEGURO
# ==========================================
def salir_sistema(request):
    if request.user.is_authenticated:
        registrar_log(request.user, "Cerró sesión en el sistema", "Autenticación")
        auth_logout(request)
    return redirect('login')

# ==========================================
# RNF-12 - FUNCIÓN DE AUDITORÍA
# ==========================================
def registrar_log(usuario, accion, modulo, detalle=""):
    if usuario.is_authenticated:
        RegistroAuditoria.objects.create(
            usuario=usuario, 
            accion=accion, 
            modulo=modulo, 
            detalle=detalle
        )
        # Refresca automáticamente el Dashboard cuando se hace un cambio
        cache.delete('dashboard_metrics')

@login_required
def auditoria_lista(request):
    logs = RegistroAuditoria.objects.all().order_by('-fecha_hora')
    return render(request, 'auditoria.html', {'logs': logs})

# ==========================================
# DASHBOARD PRINCIPAL
# ==========================================
@login_required
def dashboard_principal(request):
    # 1. Intentamos obtener la data desde la memoria Caché
    dashboard_data = cache.get('dashboard_metrics')

    if not dashboard_data:
        ingresos = Pago.objects.filter(estado='Conciliado').aggregate(total=Sum('monto_total'))['total']
        ingresos_totales = ingresos if ingresos else 0.00
        
        # 2. Combinamos las llamadas de conteo en 1 sola consulta
        pedidos_agregados = Pedido.objects.aggregate(
            total=Count('id'),
            en_ruta=Count('id', filter=Q(estado='En Ruta'))
        )
        
        productos_alerta = Stock.objects.filter(stock_actual__lte=F('stock_minimo')).count()
        tickets_pendientes = TicketSoporte.objects.exclude(estado='Resuelto').count()

        dashboard_data = {
            'ingresos_totales': ingresos_totales,
            'total_pedidos': pedidos_agregados['total'],
            'pedidos_en_ruta': pedidos_agregados['en_ruta'],
            'productos_alerta': productos_alerta,
            'tickets_pendientes': tickets_pendientes,
        }
        # 3. Guardamos los resultados por 180 segundos
        cache.set('dashboard_metrics', dashboard_data, 180)

    return render(request, 'dashboard.html', dashboard_data)

# ==========================================
# PAQ01 - GESTIÓN DE PEDIDOS
# ==========================================
@login_required
@rol_requerido('Ejecutivo Comercial')
def lista_pedidos(request):
    query = request.GET.get('q', '')
    if query:
        pedidos_list = Pedido.objects.select_related('cliente').filter(
            Q(id__icontains=query) | 
            Q(cliente__cli_razonSocial__icontains=query) | 
            Q(estado__icontains=query)
        ).order_by('-id')
    else:
        pedidos_list = Pedido.objects.select_related('cliente').all().order_by('-id')

    paginator = Paginator(pedidos_list, 10) 
    pedidos_db = paginator.get_page(request.GET.get('page'))
    return render(request, 'pedidos.html', {'pedidos': pedidos_db, 'query': query})

@login_required
@rol_requerido('Ejecutivo Comercial')
def crear_pedido(request, cliente_id):
    productos_db = Producto.objects.all()
    cliente = get_object_or_404(Cliente, id=cliente_id)
    return render(request, 'crear_pedido.html', {'productos': productos_db, 'cliente': cliente})

@login_required
@rol_requerido('Ejecutivo Comercial')
def buscar_cliente(request):
    dni = request.GET.get('dni')
    if not dni:
        return JsonResponse({'status': 'error', 'message': 'DNI/RUC no proporcionado'}, status=400)
    try:
        cliente = Cliente.objects.get(cli_ruc=dni)
        return JsonResponse({
            'status': 'ok', 
            'nombre': cliente.cli_razonSocial, 
            'direccion': cliente.cli_direccion, 
            'id': cliente.id
        })
    except Cliente.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Cliente no encontrado'}, status=404)

@login_required
@rol_requerido('Ejecutivo Comercial')
def guardar_pedido(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            carrito = data.get('carrito')
            if not carrito:
                return JsonResponse({'status': 'error', 'message': 'El carrito de compras está vacío.'}, status=400)
            cliente = Cliente.objects.get(id=data.get('cliente_id'))
            
            with transaction.atomic():
                total_acumulado = 0
                total_botellas = 0
                
                for item in carrito:
                    subtotal = float(item['precio']) * int(item['cantidad'])
                    total_acumulado += subtotal
                    total_botellas += int(item['cantidad'])
                
                descuento_aplicado = 0
                if total_botellas >= 100:
                    descuento_aplicado = total_acumulado * 0.10
                    total_acumulado -= descuento_aplicado
                    
                deuda_actual = Pedido.objects.filter(
                    cliente=cliente, 
                    estado__in=['En Evaluación', 'Aprobado', 'En Ruta']
                ).aggregate(Sum('total'))['total__sum'] or 0
                
                nuevo_saldo = float(deuda_actual) + total_acumulado
                
                if nuevo_saldo > float(cliente.linea_credito):
                    return JsonResponse({
                        'status': 'error', 
                        'message': f"Límite excedido. Deuda proyectada: S/{nuevo_saldo}"
                    }, status=400)

                nuevo_pedido = Pedido.objects.create(
                    cliente=cliente, 
                    total=total_acumulado, 
                    ped_descuento=descuento_aplicado, 
                    estado='En Evaluación'
                )
                
                producto_ids = [item['id'] for item in carrito]
                productos_dict = {p.id: p for p in Producto.objects.filter(id__in=producto_ids)}
                
                detalles = []
                for item in carrito:
                    detalles.append(DetallePedido(
                        pedido=nuevo_pedido, 
                        producto=productos_dict[int(item['id'])], 
                        cantidad=item['cantidad'], 
                        precio_unitario=item['precio'], 
                        subtotal=float(item['precio']) * int(item['cantidad'])
                    ))
                DetallePedido.objects.bulk_create(detalles)
            
            registrar_log(
                request.user, 
                f"Creó pedido #PED-00{nuevo_pedido.id}", 
                "Ventas", 
                f"Cliente: {cliente.cli_razonSocial} | Total: S/{total_acumulado}"
            )
            return JsonResponse({'status': 'ok', 'pedido_id': nuevo_pedido.id})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@rol_requerido('Ejecutivo Comercial')
def autorizar_pedido(request, pedido_id):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                pedido = Pedido.objects.select_related('cliente').get(id=pedido_id)
                if pedido.estado == 'En Evaluación':
                    detalles = DetallePedido.objects.select_related('producto__inventario').filter(pedido=pedido)
                    for detalle in detalles:
                        stock_item = detalle.producto.inventario
                        stock_item.stock_actual -= detalle.cantidad
                        stock_item.save()
                        
                        if stock_item.stock_actual <= stock_item.stock_minimo:
                            if not OrdenReabastecimiento.objects.filter(producto=detalle.producto, estado='Pendiente').exists():
                                OrdenReabastecimiento.objects.create(
                                    producto=detalle.producto, 
                                    cantidad_solicitada=stock_item.stock_minimo * 2
                                )
                    
                    pedido.estado = 'Aprobado'
                    pedido.save()
                    Pago.objects.create(pedido=pedido, monto_total=pedido.total, estado='Pendiente')
                    registrar_log(request.user, f"Autorizó pedido #PED-00{pedido.id}", "Ventas")
                    return JsonResponse({'status': 'ok'})
            return JsonResponse({'status': 'error', 'message': 'Pedido ya procesado.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def obtener_detalle_pedido(request, pedido_id):
    try:
        detalles = DetallePedido.objects.select_related('producto').filter(pedido_id=pedido_id)
        data = [{
            'producto': d.producto.prod_nombre, 
            'cantidad': d.cantidad, 
            'precio_unitario': str(d.precio_unitario), 
            'subtotal': str(d.subtotal)
        } for d in detalles]
        return JsonResponse({'status': 'ok', 'detalles': data})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@rol_requerido('Ejecutivo Comercial')
def eliminar_pedido(request, pedido_id):
    if request.method == 'POST':
        try:
            pedido = Pedido.objects.get(id=pedido_id)
            if pedido.estado != 'En Evaluación':
                return JsonResponse({'status': 'error', 'message': 'Solo se pueden eliminar pedidos en estado de evaluación.'}, status=400)
            
            pedido_id_num = pedido.id
            pedido.delete()
            registrar_log(request.user, f"Eliminó pedido #PED-00{pedido_id_num}", "Ventas")
            return JsonResponse({'status': 'ok'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

# ==========================================
# PAQ03 - GESTIÓN DE INVENTARIO
# ==========================================
@login_required
@rol_requerido('Supervisor Almacen')
def inventario_lista(request):
    if request.method == 'POST':
        with transaction.atomic():
            prod = Producto.objects.create(
                prod_codigo=request.POST.get('codigo', 'SKU-000'),
                prod_nombre=request.POST.get('nombre'), 
                prod_precio=request.POST.get('precio')
            )
            Stock.objects.create(
                producto=prod, 
                stock_actual=request.POST.get('stock_actual'), 
                stock_minimo=request.POST.get('stock_minimo')
            )
            registrar_log(request.user, f"Creó producto {prod.prod_nombre}", "Inventario")
            return redirect('inventario')
        
    productos_db = Producto.objects.all().select_related('inventario').order_by('prod_nombre')
    ordenes_reabastecimiento = OrdenReabastecimiento.objects.filter(estado='Pendiente')
    return render(request, 'inventario.html', {
        'productos': productos_db, 
        'ordenes_reabastecimiento': ordenes_reabastecimiento
    })

@login_required
@rol_requerido('Supervisor Almacen')
def editar_producto(request, producto_id):
    if request.method == 'POST':
        try:
            producto = Producto.objects.get(id=producto_id)
            producto.prod_nombre = request.POST.get('nombre')
            producto.prod_precio = request.POST.get('precio')
            producto.save()
            
            stock_item = producto.inventario
            stock_item.stock_actual = request.POST.get('stock_actual')
            stock_item.stock_minimo = request.POST.get('stock_minimo')
            stock_item.save()
            
            registrar_log(request.user, f"Editó producto {producto.prod_nombre}", "Inventario")
            return JsonResponse({'status': 'ok'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@rol_requerido('Supervisor Almacen')
def eliminar_producto(request, producto_id):
    if request.method == 'POST':
        try:
            prod = Producto.objects.get(id=producto_id)
            nombre_prod = prod.prod_nombre
            prod.delete()
            registrar_log(request.user, f"Eliminó producto {nombre_prod}", "Inventario")
            return JsonResponse({'status': 'ok'})
        except (ProtectedError, RestrictedError):
            return JsonResponse({'status': 'error', 'message': 'No se puede eliminar porque hay pedidos históricos asociados a este producto.'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@rol_requerido('Supervisor Almacen')
def recibir_reabastecimiento(request, orden_id):
    if request.method == 'POST':
        try:
            orden = OrdenReabastecimiento.objects.get(id=orden_id)
            if orden.estado == 'Pendiente':
                stock_item = orden.producto.inventario
                stock_item.stock_actual += orden.cantidad_solicitada
                stock_item.save()
                
                orden.estado = 'Recibido'
                orden.save()
                registrar_log(request.user, f"Recibió reabastecimiento #{orden.id}", "Inventario")
                return JsonResponse({'status': 'ok'})
            return JsonResponse({'status': 'error', 'message': 'Orden ya recibida.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

# ==========================================
# PAQ05 - GESTIÓN ADMINISTRATIVA
# ==========================================
@login_required
@rol_requerido('Administrador Comercial', 'Ejecutivo Comercial')
def clientes_lista(request):
    if request.method == 'POST':
        try:
            dni = request.POST.get('dni')
            if Cliente.objects.filter(cli_ruc=dni).exists():
                messages.error(request, f"Ya existe un cliente registrado con el DNI/RUC {dni}.")
            else:
                cliente = Cliente.objects.create(
                    cli_ruc=dni, 
                    cli_razonSocial=request.POST.get('nombre'), 
                    cli_direccion=request.POST.get('direccion')
                )
                registrar_log(request.user, f"Registró cliente {cliente.cli_razonSocial}", "Administración")
                messages.success(request, "Cliente registrado exitosamente.")
        except Exception as e:
            messages.error(request, f"Error al guardar cliente: {str(e)}")
        return redirect('clientes')
        
    query = request.GET.get('q', '')
    if query:
        clientes_db = Cliente.objects.filter(
            Q(cli_ruc__icontains=query) | 
            Q(cli_razonSocial__icontains=query)
        ).order_by('-id')
    else:
        clientes_db = Cliente.objects.all().order_by('-id')
        
    return render(request, 'clientes.html', {'clientes': clientes_db, 'query': query})

@login_required
@rol_requerido('Administrador Comercial', 'Ejecutivo Comercial')
def editar_cliente(request, cliente_id):
    if request.method == 'POST':
        try:
            dni = request.POST.get('dni')
            if Cliente.objects.filter(cli_ruc=dni).exclude(id=cliente_id).exists():
                return JsonResponse({'status': 'error', 'message': f'Ya existe otro cliente con el DNI/RUC {dni}.'}, status=400)
                
            cliente = Cliente.objects.get(id=cliente_id)
            cliente.cli_ruc = dni
            cliente.cli_razonSocial = request.POST.get('nombre')
            cliente.cli_direccion = request.POST.get('direccion')
            cliente.save()
            return JsonResponse({'status': 'ok'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@rol_requerido('Administrador Comercial', 'Ejecutivo Comercial')
def eliminar_cliente(request, cliente_id):
    if request.method == 'POST':
        try:
            cliente = Cliente.objects.get(id=cliente_id)
            nombre_cliente = cliente.cli_razonSocial
            cliente.delete()
            registrar_log(request.user, f"Eliminó cliente {nombre_cliente}", "Administración")
            return JsonResponse({'status': 'ok'})
        except (ProtectedError, RestrictedError):
            # Esta es la validación DB-Level que hicimos, conecta directo con SweetAlert
            return JsonResponse({
                'status': 'error', 
                'message': 'Operación denegada por seguridad. Este cliente no puede ser eliminado porque ya tiene un historial de pedidos o tickets vinculados en el sistema.'
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

# ==========================================
# PAQ02 - GESTIÓN DE PAGOS
# ==========================================
@login_required
@rol_requerido('Analista Tesoreria')
def pagos_lista(request):
    pagos_db = Pago.objects.select_related('pedido', 'pedido__cliente').all().order_by('-id')
    return render(request, 'pagos.html', {'pagos': pagos_db})

@login_required
@rol_requerido('Analista Tesoreria')
def conciliar_pago(request, pago_id):
    if request.method == 'POST':
        try:
            pago = Pago.objects.get(id=pago_id)
            if pago.estado == 'Pendiente':
                pago.codigo_operacion = request.POST.get('codigo_operacion')
                pago.metodo = request.POST.get('metodo')
                pago.estado = 'Conciliado'
                pago.save()
                registrar_log(request.user, f"Concilió pago #PAG-00{pago.id}", "Finanzas")
                return JsonResponse({'status': 'ok'})
            return JsonResponse({'status': 'error', 'message': 'Pago ya procesado.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

# ==========================================
# PAQ04 - GESTIÓN DE DISTRIBUCIÓN
# ==========================================
@login_required
@rol_requerido('Supervisor Almacen') 
def logistica_lista(request):
    if request.method == 'POST' and 'nuevo_transportista' in request.POST:
        Transportista.objects.create(
            nombre=request.POST.get('nombre'), 
            placa_vehiculo=request.POST.get('placa'), 
            telefono=request.POST.get('telefono')
        )
        return redirect('logistica')
        
    pedidos_listos = Pedido.objects.select_related('cliente', 'pago').filter(estado='Aprobado', pago__estado='Conciliado').order_by('id')
    pedidos_en_ruta = Pedido.objects.select_related('cliente', 'ordendespacho', 'ordendespacho__transportista').filter(estado='En Ruta').order_by('-id')
    transportistas = Transportista.objects.all()
    
    return render(request, 'logistica.html', {
        'pedidos_listos': pedidos_listos, 
        'pedidos_en_ruta': pedidos_en_ruta, 
        'transportistas': transportistas
    })

@login_required
@rol_requerido('Supervisor Almacen')
def generar_despacho(request, pedido_id):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                pedido = Pedido.objects.get(id=pedido_id)
                transportista = Transportista.objects.get(id=request.POST.get('transportista_id'))
                OrdenDespacho.objects.create(
                    pedido=pedido, 
                    transportista=transportista, 
                    direccion_destino=pedido.cliente.cli_direccion
                )
                pedido.estado = 'En Ruta'
                pedido.save()
                registrar_log(request.user, f"Generó despacho para #PED-00{pedido.id}", "Logística")
                return JsonResponse({'status': 'ok'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

# ==========================================
# PAQ06 - GESTIÓN DE DEVOLUCIONES
# ==========================================
@login_required
@rol_requerido('Supervisor Servicio')
def devoluciones_lista(request):
    devoluciones_db = Devolucion.objects.select_related('pedido', 'pedido__cliente').all().order_by('-id')
    pedidos_elegibles = Pedido.objects.select_related('cliente').filter(estado='En Ruta')
    return render(request, 'devoluciones.html', {
        'devoluciones': devoluciones_db, 
        'pedidos_elegibles': pedidos_elegibles
    })

@login_required
@rol_requerido('Supervisor Servicio')
def registrar_devolucion(request):
    if request.method == 'POST':
        try:
            pedido = Pedido.objects.get(id=request.POST.get('pedido_id'))
            Devolucion.objects.create(pedido=pedido, motivo=request.POST.get('motivo'))
            registrar_log(request.user, f"Registró reclamo para #PED-00{pedido.id}", "Devoluciones")
            return JsonResponse({'status': 'ok'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@rol_requerido('Supervisor Servicio')
def evaluar_devolucion(request, dev_id):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                devolucion = Devolucion.objects.select_related('pedido', 'pedido__pago').get(id=dev_id)
                decision = request.POST.get('decision')
                
                if devolucion.estado == 'En Evaluación':
                    devolucion.estado = decision
                    devolucion.save()
                    
                    if decision == 'Justificada':
                        for detalle in DetallePedido.objects.select_related('producto__inventario').filter(pedido=devolucion.pedido):
                            stock_item = detalle.producto.inventario
                            stock_item.stock_actual += detalle.cantidad
                            stock_item.save()
                        
                        devolucion.pedido.estado = 'Devuelto'
                        devolucion.pedido.save()
                        if hasattr(devolucion.pedido, 'pago'):
                            devolucion.pedido.pago.estado = 'Rechazado'
                            devolucion.pedido.pago.save()
                            
                    registrar_log(request.user, f"Evaluó devolución #DEV-00{devolucion.id}", "Devoluciones")
                    return JsonResponse({'status': 'ok'})
            return JsonResponse({'status': 'error', 'message': 'Devolución ya procesada.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

# ==========================================
# PAQ07 - ATENCIÓN AL CLIENTE
# ==========================================
@login_required
@rol_requerido('Supervisor Servicio')
def atencion_lista(request):
    tickets_db = TicketSoporte.objects.select_related('cliente', 'pedido_relacionado').all().order_by('-id')
    clientes = Cliente.objects.all()
    pedidos = Pedido.objects.select_related('cliente').all().order_by('-id')
    return render(request, 'atencion.html', {
        'tickets': tickets_db, 
        'clientes': clientes, 
        'pedidos': pedidos
    })

@login_required
@rol_requerido('Supervisor Servicio')
def crear_ticket(request):
    if request.method == 'POST':
        try:
            cliente = Cliente.objects.get(id=request.POST.get('cliente_id'))
            pedido_id = request.POST.get('pedido_id')
            pedido = Pedido.objects.get(id=pedido_id) if pedido_id else None
            
            ticket = TicketSoporte.objects.create(
                cliente=cliente, 
                pedido_relacionado=pedido,
                tipo=request.POST.get('tipo'), 
                asunto=request.POST.get('asunto'),
                descripcion=request.POST.get('descripcion')
            )
            registrar_log(request.user, f"Abrió ticket #TK-00{ticket.id}", "Soporte")
            return JsonResponse({'status': 'ok'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@rol_requerido('Supervisor Servicio')
def resolver_ticket(request, ticket_id):
    if request.method == 'POST':
        try:
            ticket = TicketSoporte.objects.get(id=ticket_id)
            if ticket.estado == 'Resuelto':
                return JsonResponse({'status': 'error', 'message': 'El ticket ya se encuentra resuelto.'}, status=400)
            ticket.respuesta_agente = request.POST.get('respuesta')
            ticket.estado = 'Resuelto'
            ticket.save()
            registrar_log(request.user, f"Resolvió ticket #TK-00{ticket.id}", "Soporte")
            return JsonResponse({'status': 'ok'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
        
import importlib
from django.template.loader import get_template
from django.http import HttpResponse
