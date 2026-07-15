from django.core.management.base import BaseCommand
from ventas.models import Caja, Producto


CAJAS = [
    ('Presencial', Caja.Tipo.MANUAL),
    ('Kio 1', Caja.Tipo.AUTOSERVICIO),
    ('Kio 2', Caja.Tipo.AUTOSERVICIO),
    ('Ventas online', Caja.Tipo.WEB),
]

CONVERTIBLES = [
    {
        'nombre': 'Combo 1 con hot dog', 'categoria': 'COMBO 01', 'codigo_vaso': '3088', 'codigo_botella': '3089',
        'descripcion_vaso': '1 cancha mediana + 1 gaseosa mediana + 1 hot dog + 1 cañonazo',
        'descripcion_botella': '1 pop mediano c/sal + 1 botella + 1 dulce + hot dog',
    },
    {
        'nombre': 'Combo 1 sin hot dog', 'categoria': 'COMBO 01', 'codigo_vaso': '2512', 'codigo_botella': '002498',
        'descripcion_vaso': 'Combo 1 sin hot dog, versión vaso',
        'descripcion_botella': '1 pop mediano c/sal + 1 gaseosa botella + 1 dulce',
    },
    {
        'nombre': 'Combo 2 con hot dog', 'categoria': 'COMBO 02', 'codigo_vaso': '2518', 'codigo_botella': '002520',
        'descripcion_vaso': '2 canchas pequeñas + 2 gaseosas pequeñas + 1 hot dog',
        'descripcion_botella': '2 pop chico c/sal + 2 botellas + 1 hot dog',
    },
    {
        'nombre': 'Combo 2 sin hot dog', 'categoria': 'COMBO 02', 'codigo_vaso': '2517', 'codigo_botella': '002519',
        'descripcion_vaso': '2 canchas pequeñas + 2 gaseosas pequeñas',
        'descripcion_botella': '2 pop chico c/sal + 2 botellas',
    },
    {
        'nombre': 'Combo 3 con hot dog', 'categoria': 'COMBO 03', 'codigo_vaso': '2485', 'codigo_botella': '002503',
        'descripcion_vaso': '1 cancha gigante + 2 gaseosas medianas + 1 hot dog',
        'descripcion_botella': '1 pop gigante c/sal + 2 botellas + 1 hot dog',
    },
    {
        'nombre': 'Combo 3 sin hot dog', 'categoria': 'COMBO 03', 'codigo_vaso': '2484', 'codigo_botella': '002502',
        'descripcion_vaso': '1 cancha gigante + 2 gaseosas medianas',
        'descripcion_botella': '1 pop gigante c/sal + 2 botellas',
    },
    {
        'nombre': 'Combo 4 con hot dog', 'categoria': 'COMBO 04', 'codigo_vaso': '2489', 'codigo_botella': '002505',
        'descripcion_vaso': '1 cancha gigante + 2 gaseosas grandes + 1 hot dog',
        'descripcion_botella': '1 pop gigante c/sal + 3 botellas + 1 hot dog',
    },
    {
        'nombre': 'Combo 4 sin hot dog', 'categoria': 'COMBO 04', 'codigo_vaso': '2488', 'codigo_botella': '002504',
        'descripcion_vaso': '1 cancha gigante + 2 gaseosas grandes',
        'descripcion_botella': '1 pop gigante c/sal + 3 botellas',
    },
    {
        'nombre': 'Combo Power', 'categoria': 'COMBOS', 'codigo_vaso': '3135', 'codigo_botella': '002834',
        'descripcion_vaso': '1 pizza personal + 1 cancha grande + 2 gaseosas pequeñas',
        'descripcion_botella': '1 pizza + 1 pop salado grande + 2 gaseosas botella',
    },
    {
        'nombre': 'Combo 1 dulce', 'categoria': 'COMBO 01 DULCE', 'codigo_vaso': '2611', 'codigo_botella': '2768',
        'descripcion_vaso': '1 pop mediano dulce + 1 gaseosa en vaso',
        'descripcion_botella': '1 pop mediano dulce + 1 botella',
    },
    {
        'nombre': 'Combo 2 dulce', 'categoria': 'COMBO 02 DULCE', 'codigo_vaso': '2612', 'codigo_botella': '2769',
        'descripcion_vaso': '2 pop chico dulce + 2 gaseosas en vaso',
        'descripcion_botella': '2 pop chico dulce + 2 botellas',
    },
    {
        'nombre': 'Combo 3 mix', 'categoria': 'COMBO 03 MIX', 'codigo_vaso': '2613', 'codigo_botella': '002770',
        'descripcion_vaso': '1 pop gigante mixto + 2 gaseosas en vaso',
        'descripcion_botella': '1 pop gigante mix + 2 botellas',
    },
    {
        'nombre': 'Combo 4 mix', 'categoria': 'COMBO 04 MIX', 'codigo_vaso': '2614', 'codigo_botella': '002771',
        'descripcion_vaso': '1 pop gigante mixto + gaseosas en vaso',
        'descripcion_botella': '1 pop gigante mix + 3 botellas',
    },
    {
        'nombre': 'Gaseosa vaso chico', 'categoria': 'BEBIDAS INDIVIDUALES', 'codigo_vaso': '2085', 'codigo_botella': '2097',
        'descripcion_vaso': 'Gaseosa individual en vaso chico', 'descripcion_botella': 'Gaseosa botella',
    },
    {
        'nombre': 'Gaseosa vaso mediano', 'categoria': 'BEBIDAS INDIVIDUALES', 'codigo_vaso': '2086', 'codigo_botella': '2097',
        'descripcion_vaso': 'Gaseosa individual en vaso mediano', 'descripcion_botella': 'Gaseosa botella',
    },
    {
        'nombre': 'Gaseosa vaso grande', 'categoria': 'BEBIDAS INDIVIDUALES', 'codigo_vaso': '2087', 'codigo_botella': '2097',
        'descripcion_vaso': 'Gaseosa individual en vaso grande', 'descripcion_botella': 'Gaseosa botella',
    },
]

# Los combos dulces/mixtos botella ya están representados por sus relaciones
# convertibles vaso → botella. Solo se mantienen aquí botellas que son productos
# individuales independientes.
DIRECTOS_BOTELLA = [
    ('Chicha botella', 'BEBIDAS INDIVIDUALES', '3090'),
    ('Gaseosa botella', 'BEBIDAS INDIVIDUALES', '2097'),
]

CODIGOS_BOTELLA_INTEGRADOS_EN_COMBO = ['2768', '2769', '002770', '002771']

INDIVIDUALES = [
    ('Gomita Ambrosito', 'DULCES', '1911'),
    ('Hot dog individual', 'COMIDAS', '1677'),
    ('Pop corn chico salado', 'POPCORN SALADO', '31'),
    ('Pop corn mediano salado', 'POPCORN SALADO', '32'),
    ('Pop corn grande salado', 'POPCORN SALADO', '33'),
    ('Pop corn gigante salado', 'POPCORN SALADO', '47'),
    ('Pop corn chico dulce', 'POPCORN DULCE', '2606'),
    ('Pop corn mediano dulce', 'POPCORN DULCE', '2607'),
    ('Pop corn grande dulce', 'POPCORN DULCE', '2608'),
    ('Pop corn gigante dulce', 'POPCORN DULCE', '2609'),
    ('Wafer', 'DULCES', '9'),
    ('Travesuras', 'DULCES', '4'),
    ('Sublime', 'DULCES', '13'),
    ('Lenteja cajita 30 gr', 'DULCES', '16'),
    ('Cañonazo', 'DULCES', '2527'),
    ('Agua San Luis', 'BEBIDAS INDIVIDUALES', '26'),
    ('Promo Yape: 2 pop salado chico', 'PROMOCIONES', '3425'),
    ('Combo Yape: 1 pop salado gigante + 2', 'PROMOCIONES', '2872'),
    ('Super pizza personal', 'COMIDAS', '2860'),
    ('Papa Inka Chips', 'SNACKS', '3331'),
    ('Combo BBVA/Plin: 1 pop salado gigante + 2', 'PROMOCIONES', '3845'),
    ('Combo Mantequilla Pop: 1 pop', 'PROMOCIONES', '3971'),
    ('Gelatines', 'DULCES', '3653'),
    ('Nachos 90 gramos', 'SNACKS', '2899'),
    ('Combo Galáctico: 1 pop gigante salado', 'PROMOCIONES', '4171'),
    ('Refil Galáctico gigante', 'PROMOCIONES', '4177'),
    ('Combo Legado: 1 pop grande salado + 1 gaseosa', 'PROMOCIONES', '4181'),
]

CODIGOS_BOTELLA_RETIRADOS = ['002097', '2750', '3539', '3541', '3559', '3561']


class Command(BaseCommand):
    help = 'Carga las cuatro cajas y el catálogo operativo editable de combos y ventas individuales.'

    def handle(self, *args, **options):
        cambios_nombre = {
            'Caja Choco': ('Presencial', Caja.Tipo.MANUAL),
            'Autoservicio 1': ('Kio 1', Caja.Tipo.AUTOSERVICIO),
            'Autoservicio 2': ('Kio 2', Caja.Tipo.AUTOSERVICIO),
            'Ventas web': ('Ventas online', Caja.Tipo.WEB),
        }
        for anterior, (nuevo, tipo) in cambios_nombre.items():
            Caja.objects.filter(nombre=anterior).update(nombre=nuevo, tipo=tipo, activa=True)

        for nombre, tipo in CAJAS:
            Caja.objects.update_or_create(nombre=nombre, defaults={'tipo': tipo, 'activa': True})

        Producto.objects.filter(codigo_botella__in=CODIGOS_BOTELLA_RETIRADOS).delete()
        # Elimina filas antiguas que repetían el mismo combo únicamente como botella.
        # La relación convertible conserva ambos códigos y ambas imágenes.
        Producto.objects.filter(
            codigo_vaso='',
            codigo_botella__in=CODIGOS_BOTELLA_INTEGRADOS_EN_COMBO,
        ).delete()

        for data in CONVERTIBLES:
            Producto.objects.update_or_create(
                codigo_vaso=data['codigo_vaso'],
                defaults={
                    **data,
                    'convertible': True,
                    'confirmado': True,
                    'activo': True,
                    'notas': 'Equivalencia cargada para operación; puede editarse desde el catálogo.',
                },
            )

        for nombre, categoria, codigo in DIRECTOS_BOTELLA:
            Producto.objects.update_or_create(
                codigo_botella=codigo,
                codigo_vaso='',
                defaults={
                    'nombre': nombre,
                    'categoria': categoria,
                    'descripcion_botella': nombre,
                    'convertible': False,
                    'confirmado': True,
                    'activo': True,
                    'notas': 'Producto vendido directamente en botella.',
                },
            )

        for nombre, categoria, codigo in INDIVIDUALES:
            Producto.objects.update_or_create(
                codigo_vaso=codigo,
                defaults={
                    'nombre': nombre,
                    'categoria': categoria,
                    'codigo_botella': '',
                    'descripcion_vaso': nombre,
                    'descripcion_botella': '',
                    'convertible': False,
                    'confirmado': True,
                    'activo': True,
                    'notas': 'Venta individual.',
                },
            )
        self.stdout.write(self.style.SUCCESS('Catálogo actualizado: combos, bebidas y ventas individuales cargados.'))
