from datetime import date
from django.core.management.base import BaseCommand
from ventas.models import Caja, Cierre, DetalleCierre, Jornada


class Command(BaseCommand):
    help = 'Crea una jornada de demostración: 10 unidades vaso y 8 nuevas convertidas a botella.'

    def handle(self, *args, **options):
        caja = Caja.objects.get(nombre='Presencial')
        jornada, _ = Jornada.objects.get_or_create(fecha=date.today(), caja=caja, defaults={'observaciones': 'Demostración del cálculo acumulado.'})
        jornada.cierres.all().delete()
        primero = Cierre.objects.create(jornada=jornada, numero=1, modalidad_periodo=Cierre.Modalidad.VASO, confirmado=True)
        DetalleCierre.objects.create(cierre=primero, codigo_leido='3088', cantidad_acumulada=10)
        segundo = Cierre.objects.create(
            jornada=jornada,
            numero=2,
            modalidad_periodo=Cierre.Modalidad.BOTELLA,
            motivo_cambio='Agotamiento de jarabe',
            confirmado=True,
        )
        DetalleCierre.objects.create(cierre=segundo, codigo_leido='3088', cantidad_acumulada=18)
        self.stdout.write(self.style.SUCCESS('Demostración creada: el resumen debe mostrar 3088 × 10 y 3089 × 8.'))
