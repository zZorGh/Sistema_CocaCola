from django.urls import path  # type: ignore[reportMissingModuleSource]
from django.contrib.auth.views import LoginView  # type: ignore[reportMissingModuleSource]
from . import views 

urlpatterns = [
    # Autenticación
    path('login/', LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', views.salir_sistema, name='logout'),

    # Dashboard principal
    path('', views.dashboard_principal, name='dashboard'),
    
    # Módulos Principales (CUS)
    path('pedidos/', views.lista_pedidos, name='pedidos'),
    path('pagos/', views.pagos_lista, name='pagos'),
    path('inventario/', views.inventario_lista, name='inventario'),
    path('distribucion/', views.logistica_lista, name='logistica'),
    path('clientes/', views.clientes_lista, name='clientes'),
    path('devoluciones/', views.devoluciones_lista, name='devoluciones'),
    path('atencion/', views.atencion_lista, name='atencion'),
    
    # Admin Setup
    path('auditoria/', views.auditoria_lista, name='auditoria'),

    # ---- RUTAS SECUNDARIAS (Acciones internas) ----
    path('pedidos/crear/<int:cliente_id>/', views.crear_pedido, name='crear_pedido'),
    path('pedidos/buscar_cliente/', views.buscar_cliente, name='buscar_cliente'),
    path('pedidos/guardar/', views.guardar_pedido, name='guardar_pedido'),
    path('pedidos/autorizar/<int:pedido_id>/', views.autorizar_pedido, name='autorizar_pedido'),
    path('pedidos/detalle/<int:pedido_id>/', views.obtener_detalle_pedido, name='obtener_detalle_pedido'),
    path('pedidos/eliminar/<int:pedido_id>/', views.eliminar_pedido, name='eliminar_pedido'),
    
    path('inventario/editar/<int:producto_id>/', views.editar_producto, name='editar_producto'),
    path('inventario/eliminar/<int:producto_id>/', views.eliminar_producto, name='eliminar_producto'),
    path('inventario/reabastecer/<int:orden_id>/', views.recibir_reabastecimiento, name='recibir_reabastecimiento'),
    
    path('clientes/editar/<int:cliente_id>/', views.editar_cliente, name='editar_cliente'),
    path('clientes/eliminar/<int:cliente_id>/', views.eliminar_cliente, name='eliminar_cliente'),
    
    path('pagos/conciliar/<int:pago_id>/', views.conciliar_pago, name='conciliar_pago'),
    
    path('logistica/despachar/<int:pedido_id>/', views.generar_despacho, name='generar_despacho'),
    
    path('devoluciones/registrar/', views.registrar_devolucion, name='registrar_devolucion'),
    path('devoluciones/evaluar/<int:dev_id>/', views.evaluar_devolucion, name='evaluar_devolucion'),
    
    path('atencion/crear/', views.crear_ticket, name='crear_ticket'),
    path('atencion/resolver/<int:ticket_id>/', views.resolver_ticket, name='resolver_ticket'),
]