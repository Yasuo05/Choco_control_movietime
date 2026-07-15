from django.core.management.base import BaseCommand

from ventas.models import Producto
from ventas.services import clave_codigo


class Command(BaseCommand):
    help = 'Elimina filas botella redundantes cuando el combo convertible ya contiene ambos códigos.'

    def handle(self, *args, **options):
        convertibles = list(
            Producto.objects.filter(activo=True, convertible=True)
            .exclude(codigo_vaso='')
            .exclude(codigo_botella='')
        )
        origenes_por_botella: dict[str, list[Producto]] = {}
        for producto in convertibles:
            origenes_por_botella.setdefault(clave_codigo(producto.codigo_botella), []).append(producto)

        eliminados: list[str] = []
        candidatos = Producto.objects.filter(activo=True, convertible=False, codigo_vaso='').exclude(codigo_botella='')
        for producto in candidatos:
            origenes = origenes_por_botella.get(clave_codigo(producto.codigo_botella), [])
            if len(origenes) == 1:
                eliminados.append(f'{producto.nombre} ({producto.codigo_botella})')
                producto.delete()

        if eliminados:
            self.stdout.write(self.style.SUCCESS('Duplicados eliminados:'))
            for nombre in eliminados:
                self.stdout.write(f' - {nombre}')
        else:
            self.stdout.write(self.style.SUCCESS('No se encontraron filas botella duplicadas para eliminar.'))
