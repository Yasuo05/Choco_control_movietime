from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ventas.models import Caja, Jornada, Cierre


CAMBIOS = [
    ('Caja Choco', 'Presencial', Caja.Tipo.MANUAL),
    ('Autoservicio 1', 'Kio 1', Caja.Tipo.AUTOSERVICIO),
    ('Autoservicio 2', 'Kio 2', Caja.Tipo.AUTOSERVICIO),
    ('Ventas web', 'Ventas online', Caja.Tipo.WEB),
]


class Command(BaseCommand):
    help = 'Renombra las vías de venta antiguas sin perder jornadas ni cierres existentes.'

    @transaction.atomic
    def handle(self, *args, **options):
        cambios_realizados = []
        for nombre_anterior, nombre_nuevo, tipo in CAMBIOS:
            antigua = Caja.objects.filter(nombre=nombre_anterior).first()
            nueva = Caja.objects.filter(nombre=nombre_nuevo).first()

            if antigua and nueva and antigua.pk != nueva.pk:
                if Jornada.objects.filter(caja__in=[antigua, nueva]).exists():
                    raise CommandError(
                        f'Existen registros tanto para "{nombre_anterior}" como para "{nombre_nuevo}". '
                        'No se mezclaron automáticamente para evitar alterar el orden histórico de las boletas.'
                    )
                antigua.delete()
                nueva.tipo = tipo
                nueva.activa = True
                nueva.save(update_fields=['tipo', 'activa'])
                cambios_realizados.append(f'{nombre_anterior} → {nombre_nuevo}')
            elif antigua:
                antigua.nombre = nombre_nuevo
                antigua.tipo = tipo
                antigua.activa = True
                antigua.save(update_fields=['nombre', 'tipo', 'activa'])
                cambios_realizados.append(f'{nombre_anterior} → {nombre_nuevo}')
            elif nueva:
                nueva.tipo = tipo
                nueva.activa = True
                nueva.save(update_fields=['tipo', 'activa'])
            else:
                Caja.objects.create(nombre=nombre_nuevo, tipo=tipo, activa=True)
                cambios_realizados.append(f'Creada: {nombre_nuevo}')

        if cambios_realizados:
            self.stdout.write(self.style.SUCCESS('Vías de venta actualizadas: ' + '; '.join(cambios_realizados)))
        else:
            self.stdout.write(self.style.SUCCESS('Las vías de venta ya estaban actualizadas.'))
        self.stdout.write(
            self.style.SUCCESS(
                'Regla activa: las boletas acumuladas se restan dentro de cada vía y luego se suman entre vías.'
            )
        )
