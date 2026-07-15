from django.contrib import admin
from .models import Caja, Cierre, DetalleCierre, Jornada, Producto


@admin.register(Caja)
class CajaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'activa')
    list_filter = ('tipo', 'activa')


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'categoria', 'codigo_vaso', 'codigo_botella', 'convertible', 'confirmado')
    list_filter = ('categoria', 'convertible', 'confirmado', 'activo')
    search_fields = ('nombre', 'codigo_vaso', 'codigo_botella')


class DetalleCierreInline(admin.TabularInline):
    model = DetalleCierre
    extra = 0


@admin.register(Cierre)
class CierreAdmin(admin.ModelAdmin):
    list_display = ('jornada', 'numero', 'modalidad_periodo', 'confirmado', 'creado_en')
    list_filter = ('modalidad_periodo', 'confirmado')
    inlines = [DetalleCierreInline]
    filter_horizontal = ('productos_convertir',)


@admin.register(Jornada)
class JornadaAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'caja', 'creada_en')
    list_filter = ('caja', 'fecha')
