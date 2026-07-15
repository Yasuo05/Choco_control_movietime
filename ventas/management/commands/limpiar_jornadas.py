from django.core.management.base import BaseCommand
from ventas.models import Jornada


class Command(BaseCommand):
    help = 'Elimina jornadas y cierres registrados, conservando cajas y catálogo de productos.'

    def handle(self, *args, **options):
        cantidad = Jornada.objects.count()
        Jornada.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'Se eliminaron {cantidad} jornada(s). El catálogo se conserva.'))
