from django.db import models  # type: ignore[reportMissingModuleSource]
from django.contrib.auth.models import User  # type: ignore[reportMissingModuleSource]

# ==========================================
# TB_CLIENTE (Diccionario de Datos Oficial)
# ==========================================
class Cliente(models.Model):
    CANAL_CHOICES = [
        ('Mayorista', 'Mayorista'),
        ('Minorista', 'Minorista'),
    ]
    ESTADO_CHOICES = [
        ('Activo', 'Activo'),
        ('Inactivo', 'Inactivo'),
    ]
    
    cli_ruc = models.CharField(max_length=11, unique=True)
    cli_razonSocial = models.CharField(max_length=150)
    cli_direccion = models.CharField(max_length=250)
    cli_canal = models.CharField(max_length=20, choices=CANAL_CHOICES, default='Minorista')
    cli_estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='Activo')
    linea_credito = models.DecimalField(max_digits=10, decimal_places=2, default=5000.00)

    @property
    def dni(self):
        return self.cli_ruc
        
    @property
    def nombre(self):
        return self.cli_razonSocial

    @property
    def direccion(self):
        return self.cli_direccion

    def __str__(self):
        return f"{self.cli_razonSocial} (RUC: {self.cli_ruc})"

    class Meta:
        db_table = 'TB_CLIENTE'
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'

# ==========================================
# TB_PRODUCTO (Catálogo de SKU)
# ==========================================
class Producto(models.Model):
    prod_codigo = models.CharField(max_length=20, unique=True)
    prod_nombre = models.CharField(max_length=100)
    prod_precio = models.DecimalField(max_digits=10, decimal_places=2)
    prod_envase = models.CharField(max_length=50, default='PET 3L')

    @property
    def nombre(self):
        return self.prod_nombre

    @property
    def precio(self):
        return self.prod_precio

    def __str__(self):
        return self.prod_nombre

    class Meta:
        db_table = 'TB_PRODUCTO'
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'

# ==========================================
# TB_STOCK (Entidad Independiente de Almacén)
# ==========================================
class Stock(models.Model):
    producto = models.OneToOneField(Producto, on_delete=models.CASCADE, related_name='inventario')
    stock_actual = models.IntegerField(default=100)
    stock_minimo = models.IntegerField(default=10)
    fecha_vencimiento = models.DateField(null=True, blank=True)
    estado_inventario = models.CharField(max_length=20, default='Normal')

    def __str__(self):
        return f"Inventario de {self.producto.prod_nombre}: {self.stock_actual}"

    class Meta:
        db_table = 'TB_STOCK'
        verbose_name = 'Stock'
        verbose_name_plural = 'Stocks'

# ==========================================
# TB_PEDIDO (Ventas con Tracking Financiero)
# ==========================================
class Pedido(models.Model):
    ESTADO_CHOICES = [
        ('En Evaluación', 'En Evaluación'),
        ('Aprobado', 'Aprobado'),
        ('En Ruta', 'En Ruta'),
        ('Devuelto', 'Devuelto'),
    ]
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='En Evaluación', db_index=True)
    ped_costoEnvio = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    ped_descuento = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    fecha_entrega = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"Pedido #PED-00{self.id} - {self.cliente.cli_razonSocial}"

    class Meta:
        db_table = 'TB_PEDIDO'
        verbose_name = 'Pedido'
        verbose_name_plural = 'Pedidos'

class DetallePedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.IntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.cantidad} x {self.producto.prod_nombre} (Pedido #{self.pedido.id})"

    class Meta:
        db_table = 'TB_DETALLE_PEDIDO'
        verbose_name = 'Detalle de Pedido'
        verbose_name_plural = 'Detalles de Pedidos'

# ==========================================
# COMPLEMENTOS OPERATIVOS DEL SISTEMA
# ==========================================
class Pago(models.Model):
    pedido = models.OneToOneField(Pedido, on_delete=models.CASCADE)
    monto_total = models.DecimalField(max_digits=10, decimal_places=2)
    codigo_operacion = models.CharField(max_length=50, blank=True, null=True)
    metodo = models.CharField(max_length=50, blank=True, null=True)
    estado = models.CharField(max_length=20, default='Pendiente', db_index=True)

    def __str__(self):
        return f"Pago de Pedido #{self.pedido.id} - Estado: {self.estado}"

    class Meta:
        db_table = 'TB_PAGO'
        verbose_name = 'Pago'
        verbose_name_plural = 'Pagos'

class Transportista(models.Model):
    nombre = models.CharField(max_length=100)
    placa_vehiculo = models.CharField(max_length=20)
    telefono = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.nombre} ({self.placa_vehiculo})"

    class Meta:
        db_table = 'TB_TRANSPORTISTA'
        verbose_name = 'Transportista'
        verbose_name_plural = 'Transportistas'

class OrdenDespacho(models.Model):
    pedido = models.OneToOneField(Pedido, on_delete=models.CASCADE)
    transportista = models.ForeignKey(Transportista, on_delete=models.CASCADE)
    direccion_destino = models.CharField(max_length=200)
    fecha_despacho = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Despacho Pedido #{self.pedido.id} - {self.transportista.nombre}"

    class Meta:
        db_table = 'TB_ORDEN_DESPACHO'
        verbose_name = 'Orden de Despacho'
        verbose_name_plural = 'Órdenes de Despacho'

class Devolucion(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE)
    motivo = models.TextField()
    estado = models.CharField(max_length=20, default='En Evaluación')
    fecha_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Devolución Pedido #{self.pedido.id} - Estado: {self.estado}"

    class Meta:
        db_table = 'TB_DEVOLUCION'
        verbose_name = 'Devolución'
        verbose_name_plural = 'Devoluciones'

class TicketSoporte(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    pedido_relacionado = models.ForeignKey(Pedido, on_delete=models.SET_NULL, null=True, blank=True)
    tipo = models.CharField(max_length=50)
    asunto = models.CharField(max_length=150)
    descripcion = models.TextField()
    respuesta_agente = models.TextField(blank=True, null=True)
    estado = models.CharField(max_length=20, default='Abierto', db_index=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Ticket #TK-00{self.id} - {self.asunto}"

    class Meta:
        db_table = 'TB_TICKET_SOPORTE'
        verbose_name = 'Ticket de Soporte'
        verbose_name_plural = 'Tickets de Soporte'

class RegistroAuditoria(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    accion = models.CharField(max_length=150)
    modulo = models.CharField(max_length=100)
    detalle = models.TextField(blank=True)
    fecha_hora = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Auditoría: {self.usuario.username} - {self.accion}"

    class Meta:
        db_table = 'TB_REGISTRO_AUDITORIA'
        verbose_name = 'Registro de Auditoría'
        verbose_name_plural = 'Registros de Auditoría'

class OrdenReabastecimiento(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad_solicitada = models.IntegerField()
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, default='Pendiente')

    def __str__(self):
        return f"Reabastecimiento {self.producto.prod_nombre} - Cantidad: {self.cantidad_solicitada}"

    class Meta:
        db_table = 'TB_ORDEN_REABASTECIMIENTO'
        verbose_name = 'Orden de Reabastecimiento'
        verbose_name_plural = 'Órdenes de Reabastecimiento'