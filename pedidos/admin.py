from django.contrib import admin
from .models import (
    Cliente,
    Producto,
    Stock,
    Pedido,
    DetallePedido,
    Pago,
    Transportista,
    OrdenDespacho,
    Devolucion,
    TicketSoporte,
    RegistroAuditoria,
    OrdenReabastecimiento
)

# Registramos nuestras tablas para poder verlas en el panel
admin.site.register(Cliente)
admin.site.register(Producto)
admin.site.register(Stock)
admin.site.register(Pedido)
admin.site.register(DetallePedido)
admin.site.register(Pago)
admin.site.register(Transportista)
admin.site.register(OrdenDespacho)
admin.site.register(Devolucion)
admin.site.register(TicketSoporte)
admin.site.register(RegistroAuditoria)
admin.site.register(OrdenReabastecimiento)