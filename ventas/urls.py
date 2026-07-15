from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('procesar-dia/', views.procesar_dia, name='procesar_dia'),
    path('procesar-dia/analizando/', views.procesando_lote, name='procesando_lote'),
    path('procesar-dia/ejecutar/', views.ejecutar_analisis_lote, name='ejecutar_analisis_lote'),
    path('procesar-dia/revisar/', views.revisar_lote, name='revisar_lote'),
    path('dia/<str:fecha_iso>/', views.resumen_dia, name='resumen_dia'),
    path('dia/<str:fecha_iso>/eliminar/', views.eliminar_registros_dia, name='eliminar_registros_dia'),
    path('dia/<str:fecha_iso>/ayuda-escritura/', views.ayuda_escritura_upbase, name='ayuda_escritura_upbase'),
    path('dia/<str:fecha_iso>/ayuda-escritura/iniciar/', views.iniciar_escritura_upbase, name='iniciar_escritura_upbase'),
    path('dia/<str:fecha_iso>/exportar/csv/', views.exportar_dia_csv, name='exportar_dia_csv'),
    path('dia/<str:fecha_iso>/exportar/xlsx/', views.exportar_dia_xlsx, name='exportar_dia_xlsx'),
    path('cajas/', views.cajas_lista, name='cajas_lista'),
    path('cajas/nueva/', views.caja_nueva, name='caja_nueva'),
    path('productos/', views.productos_lista, name='productos_lista'),
    path('productos/nuevo/', views.producto_nuevo, name='producto_nuevo'),
    path('productos/<int:pk>/editar/', views.producto_editar, name='producto_editar'),
    path('productos/<int:pk>/eliminar/', views.producto_eliminar, name='producto_eliminar'),
    path('jornadas/nueva/', views.jornada_nueva, name='jornada_nueva'),
    path('jornadas/<int:pk>/', views.jornada_detalle, name='jornada_detalle'),
    path('jornadas/<int:jornada_pk>/cierres/nuevo/', views.cierre_nuevo, name='cierre_nuevo'),
    path('cierres/<int:pk>/editar/', views.cierre_editar, name='cierre_editar'),
    path('cierres/<int:pk>/revisar/', views.cierre_revisar, name='cierre_revisar'),
    path('jornadas/<int:pk>/exportar/csv/', views.exportar_csv, name='exportar_csv'),
    path('jornadas/<int:pk>/exportar/xlsx/', views.exportar_xlsx, name='exportar_xlsx'),
]
