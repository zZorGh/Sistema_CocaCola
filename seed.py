import os
import django

# Conectar el script con la configuración de tu proyecto
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Sistema_CocaCola.settings')
django.setup()

from django.contrib.auth.models import User, Group
from pedidos.models import Cliente, Producto, Stock, Transportista

print("Iniciando poblamiento de la base de datos...")

# 1. Crear Grupos de Seguridad (Roles)
roles = [
    'Ejecutivo Comercial', 
    'Analista Tesoreria', 
    'Supervisor Almacen', 
    'Supervisor Servicio'
]
for rol in roles:
    grupo, creado = Group.objects.get_or_create(name=rol)
    if creado:
        print(f"✅ Grupo creado: {rol}")

# 2. Crear Superusuario (Admin)
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@cocacola.com', 'admin123')
    print("✅ Superusuario 'admin' creado (Clave: admin123)")

# 3. Crear Cliente de Prueba
cliente, creado = Cliente.objects.get_or_create(
    cli_ruc='20100100100',
    defaults={
        'cli_razonSocial': 'Bodega Central S.A.C.',
        'cli_direccion': 'Av. Principal 123, Lima'
    }
)
if creado:
    print("✅ Cliente de prueba creado: Bodega Central")

# 4. Crear Transportista de Prueba
trans, creado = Transportista.objects.get_or_create(
    placa_vehiculo='ABC-999',
    defaults={
        'nombre': 'Juan Perez (Ruta 1)',
        'telefono': '987654321'
    }
)
if creado:
    print("✅ Transportista creado: Juan Perez")

# 5. Catálogo Base y Stock
catalogo = [
    {'codigo': 'SKU-001', 'nombre': 'Inka Kola 3L', 'precio': 8.50, 'stock': 500, 'min': 50},
    {'codigo': 'SKU-002', 'nombre': 'Coca-Cola 3L', 'precio': 9.00, 'stock': 400, 'min': 50},
    {'codigo': 'SKU-003', 'nombre': 'Fanta 1.5L', 'precio': 4.50, 'stock': 200, 'min': 30},
    {'codigo': 'SKU-004', 'nombre': 'Sprite 1.5L', 'precio': 4.50, 'stock': 150, 'min': 30},
    {'codigo': 'SKU-005', 'nombre': 'Agua San Luis 2.5L', 'precio': 3.00, 'stock': 800, 'min': 100},
]

for item in catalogo:
    producto, p_creado = Producto.objects.get_or_create(
        prod_codigo=item['codigo'],
        defaults={
            'prod_nombre': item['nombre'],
            'prod_precio': item['precio']
        }
    )
    if p_creado:
        Stock.objects.create(
            producto=producto,
            stock_actual=item['stock'],
            stock_minimo=item['min']
        )
        print(f"✅ Producto creado: {item['nombre']} (Stock: {item['stock']})")

print("\n🚀 ¡Poblamiento completado! El sistema está listo para operar.")