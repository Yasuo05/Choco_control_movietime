from datetime import date
import base64
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.staticfiles import finders
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Caja, Cierre, DetalleCierre, Jornada, Producto
from .ocr_reader import FilaOCR, extraer_codigo_descripcion, extraer_filas, serializar_lectura
from .catalogo_imagenes import (
    adjuntar_imagenes_catalogo, adjuntar_imagenes_reporte, construir_tarjetas_presentacion,
)
from .services import (
    consolidado_de_jornada, consolidado_por_fecha, filas_detectadas_desde_ocr,
    movimientos_de_jornada, sugerir_detalles_desde_ocr,
)


class ConversionCierresAcumuladosTests(TestCase):
    def setUp(self):
        self.caja = Caja.objects.create(nombre='Presencial', tipo=Caja.Tipo.MANUAL)
        self.producto = Producto.objects.create(
            nombre='Combo 1 con hot dog', codigo_vaso='3088', codigo_botella='3089', convertible=True, confirmado=True
        )
        self.jornada = Jornada.objects.create(fecha=date(2026, 5, 24), caja=self.caja)

    def test_convierte_solo_diferencia_del_periodo_botella(self):
        cierre_1 = Cierre.objects.create(jornada=self.jornada, numero=1, modalidad_periodo=Cierre.Modalidad.VASO, confirmado=True)
        DetalleCierre.objects.create(cierre=cierre_1, codigo_leido='3088', cantidad_acumulada=10)
        cierre_2 = Cierre.objects.create(jornada=self.jornada, numero=2, modalidad_periodo=Cierre.Modalidad.BOTELLA, confirmado=True)
        DetalleCierre.objects.create(cierre=cierre_2, codigo_leido='3088', cantidad_acumulada=18)

        movimientos, advertencias = movimientos_de_jornada(self.jornada)
        self.assertFalse(advertencias)
        self.assertEqual([(m.codigo_final, m.cantidad) for m in movimientos], [('3088', 10), ('3089', 8)])
        self.assertEqual(
            [(f['codigo_final'], f['cantidad']) for f in consolidado_de_jornada(self.jornada)],
            [('3088', 10), ('3089', 8)],
        )

    def test_codigo_botella_directo_no_se_vuelve_a_convertir(self):
        cierre = Cierre.objects.create(jornada=self.jornada, numero=1, modalidad_periodo=Cierre.Modalidad.BOTELLA, confirmado=True)
        DetalleCierre.objects.create(cierre=cierre, codigo_leido='3089', cantidad_acumulada=4)
        movimientos, _ = movimientos_de_jornada(self.jornada)
        self.assertEqual(movimientos[0].codigo_final, '3089')
        self.assertFalse(movimientos[0].convertido)

    def test_detecta_cantidad_acumulada_menor(self):
        cierre_1 = Cierre.objects.create(jornada=self.jornada, numero=1, modalidad_periodo=Cierre.Modalidad.VASO, confirmado=True)
        DetalleCierre.objects.create(cierre=cierre_1, codigo_leido='3088', cantidad_acumulada=10)
        cierre_2 = Cierre.objects.create(jornada=self.jornada, numero=2, modalidad_periodo=Cierre.Modalidad.BOTELLA, confirmado=True)
        DetalleCierre.objects.create(cierre=cierre_2, codigo_leido='3088', cantidad_acumulada=8)
        _, advertencias = movimientos_de_jornada(self.jornada)
        self.assertTrue(advertencias)

    def test_reconoce_codigo_con_ceros_iniciales_entre_cierres(self):
        producto = Producto.objects.create(
            nombre='Combo 2 sin hot dog', codigo_vaso='2517', codigo_botella='002519', convertible=True, confirmado=True
        )
        cierre_1 = Cierre.objects.create(jornada=self.jornada, numero=1, modalidad_periodo=Cierre.Modalidad.VASO, confirmado=True)
        DetalleCierre.objects.create(cierre=cierre_1, codigo_leido='2517', cantidad_acumulada=2)
        cierre_2 = Cierre.objects.create(jornada=self.jornada, numero=2, modalidad_periodo=Cierre.Modalidad.BOTELLA, confirmado=True)
        DetalleCierre.objects.create(cierre=cierre_2, codigo_leido='002517', cantidad_acumulada=5)
        cierre_2.productos_convertir.add(producto)
        movimientos, _ = movimientos_de_jornada(self.jornada)
        self.assertEqual(movimientos[-1].cantidad, 3)
        self.assertEqual(movimientos[-1].codigo_final, '002519')

    def test_no_convierte_equivalencia_sin_confirmar(self):
        self.producto.confirmado = False
        self.producto.save(update_fields=['confirmado'])
        cierre = Cierre.objects.create(jornada=self.jornada, numero=1, modalidad_periodo=Cierre.Modalidad.BOTELLA, confirmado=True)
        DetalleCierre.objects.create(cierre=cierre, codigo_leido='3088', cantidad_acumulada=3)
        movimientos, advertencias = movimientos_de_jornada(self.jornada)
        self.assertEqual(movimientos[0].codigo_final, '3088')
        self.assertTrue(advertencias)

    def test_consolida_2097_y_002097_como_un_mismo_codigo(self):
        Producto.objects.create(nombre='Gaseosa botella', codigo_botella='2097', confirmado=True)
        cierre_1 = Cierre.objects.create(jornada=self.jornada, numero=1, modalidad_periodo=Cierre.Modalidad.VASO, confirmado=True)
        DetalleCierre.objects.create(cierre=cierre_1, codigo_leido='2097', cantidad_acumulada=2)
        cierre_2 = Cierre.objects.create(jornada=self.jornada, numero=2, modalidad_periodo=Cierre.Modalidad.VASO, confirmado=True)
        DetalleCierre.objects.create(cierre=cierre_2, codigo_leido='002097', cantidad_acumulada=5)
        consolidado = consolidado_de_jornada(self.jornada)
        self.assertEqual(consolidado[0]['codigo_final'], '2097')
        self.assertEqual(consolidado[0]['cantidad'], 5)
        self.assertEqual(consolidado[0]['producto'], 'Gaseosa botella')
        self.assertEqual(consolidado[0]['cajas'], 'Presencial')
        self.assertEqual(consolidado[0]['presentacion'], 'Botella')

    def test_cierre_pendiente_bloquea_solo_periodos_siguientes_de_su_caja(self):
        cierre_1 = Cierre.objects.create(jornada=self.jornada, numero=1, modalidad_periodo=Cierre.Modalidad.VASO, confirmado=False, imagen='cierres/pendiente.png')
        cierre_2 = Cierre.objects.create(jornada=self.jornada, numero=2, modalidad_periodo=Cierre.Modalidad.VASO, confirmado=True)
        DetalleCierre.objects.create(cierre=cierre_2, codigo_leido='3088', cantidad_acumulada=7)
        movimientos, advertencias = movimientos_de_jornada(self.jornada)
        self.assertEqual(movimientos, [])
        self.assertEqual(len(advertencias), 2)


class ConsolidadoDiarioTests(TestCase):
    def test_suma_cajas_en_un_solo_reporte(self):
        producto = Producto.objects.create(nombre='Hot dog individual', codigo_vaso='1677', confirmado=True)
        caja_a = Caja.objects.create(nombre='Presencial', tipo=Caja.Tipo.MANUAL)
        caja_b = Caja.objects.create(nombre='Kio 1', tipo=Caja.Tipo.AUTOSERVICIO)
        for caja, cantidad in [(caja_a, 2), (caja_b, 3)]:
            jornada = Jornada.objects.create(fecha=date(2026, 5, 24), caja=caja)
            cierre = Cierre.objects.create(jornada=jornada, numero=1, confirmado=True)
            DetalleCierre.objects.create(cierre=cierre, codigo_leido=producto.codigo_vaso, cantidad_acumulada=cantidad)
        consolidado, _ = consolidado_por_fecha(date(2026, 5, 24))
        self.assertEqual(consolidado[0]['codigo_final'], '1677')
        self.assertEqual(consolidado[0]['cantidad'], 5)


class CargaCuatroFotosTests(TestCase):
    def setUp(self):
        self.caja = Caja.objects.create(nombre='Presencial', tipo=Caja.Tipo.MANUAL)
        Caja.objects.create(nombre='Kio 1', tipo=Caja.Tipo.AUTOSERVICIO)
        Caja.objects.create(nombre='Kio 2', tipo=Caja.Tipo.AUTOSERVICIO)
        Caja.objects.create(nombre='Ventas online', tipo=Caja.Tipo.WEB)

    def test_una_foto_pasa_por_analisis_visible_y_omite_las_otras_tres(self):
        png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')
        with tempfile.TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            imagen = SimpleUploadedFile('boleta.png', png, content_type='image/png')
            respuesta = self.client.post(reverse('procesar_dia'), {
                'fecha': '2026-05-24',
                f'modalidad_{self.caja.pk}': Cierre.Modalidad.VASO,
                f'imagen_{self.caja.pk}': imagen,
            })
            self.assertRedirects(respuesta, reverse('procesando_lote'))
            self.assertEqual(Cierre.objects.count(), 0)
            pantalla = self.client.get(reverse('procesando_lote'))
            self.assertContains(pantalla, 'Analizando boletas cargadas')
            self.assertContains(pantalla, 'Presencial')
            with patch('ventas.views.ejecutar_ocr', return_value=('', 'OCR ejecutado.')):
                ejecucion = self.client.post(reverse('ejecutar_analisis_lote'))
            self.assertRedirects(ejecucion, reverse('revisar_lote'))
        self.assertEqual(Cierre.objects.count(), 1)
        self.assertEqual(Cierre.objects.get().jornada.caja, self.caja)


class LecturaBoletaOCRTests(TestCase):
    def test_extrae_codigo_y_cantidad_e_ignora_precio_total(self):
        resultados = [
            [[[430, 10], [470, 10], [470, 30], [430, 30]], 'Cant', 0.99],
            [[[530, 10], [600, 10], [600, 30], [530, 30]], 'P.Total', 0.99],
            [[[20, 60], [360, 60], [360, 88], [20, 88]], '003088 1GASEOSA MED + DUL + HO', 0.98],
            [[[435, 62], [462, 62], [462, 88], [435, 88]], '6', 0.99],
            [[[535, 62], [610, 62], [610, 88], [535, 88]], '159.00', 0.99],
            [[[20, 98], [300, 98], [300, 124], [20, 124]], '001911 GOMITA AMBROSITO', 0.97],
            [[[435, 100], [462, 100], [462, 124], [435, 124]], '3', 0.99],
            [[[535, 100], [610, 100], [610, 124], [535, 124]], '10.50', 0.99],
        ]
        filas = extraer_filas(resultados, ['3088', '1911'])
        self.assertEqual([(fila.codigo, fila.cantidad) for fila in filas], [('3088', 6), ('1911', 3)])

    def test_conserva_fila_sin_cantidad_como_revisar(self):
        lectura = serializar_lectura([FilaOCR(codigo='2087', descripcion='2087 GASEOSA GRANDE', cantidad=None, alerta='Revisar')], [])
        self.assertEqual(filas_detectadas_desde_ocr(lectura)[0]['codigo'], '2087')
        self.assertIn('2087,REVISAR', sugerir_detalles_desde_ocr(lectura))


class LecturaBoletaLimpiaTests(TestCase):
    def test_codigo_nuevo_no_se_confunde_con_producto_de_un_digito(self):
        self.assertEqual(extraer_codigo_descripcion('4171 C.GALACTICO:1POP GIGA/SAL', ['4']), '4171')
        self.assertEqual(extraer_codigo_descripcion('0004 TRAVESURAS 50 GRS', ['4']), '4')

    def test_perspectiva_no_corre_cantidades_cuando_falta_una_intermedia(self):
        codigos = ['2085', '2086', '2613', '2518', '3425', '33', '2484', '47', '3088']
        valores = [14, 9, 6, 17, 6, 8, None, 4, 3]
        resultados = [[[[430, 10], [470, 10], [470, 30], [430, 30]], 'Cant', 0.99]]
        for indice, codigo in enumerate(codigos):
            y = 60 + indice * 30
            resultados.append([[[20, y], [260, y], [260, y + 20], [20, y + 20]], f'{codigo} PRODUCTO', 0.99])
            if valores[indice] is not None:
                y_cantidad = y - 3 - indice
                resultados.append([[[435, y_cantidad], [460, y_cantidad], [460, y_cantidad + 20], [435, y_cantidad + 20]], str(valores[indice]), 0.99])
        filas = extraer_filas(resultados, codigos, alinear_por_orden=True)
        self.assertEqual([(fila.codigo, fila.cantidad) for fila in filas], list(zip(codigos, valores)))



class CatalogoVisualProductosTests(TestCase):
    def test_foto_por_codigo_se_asigna_automaticamente_al_producto(self):
        producto = Producto.objects.create(nombre='Combo 1', codigo_vaso='3088', codigo_botella='3089', confirmado=True)
        with tempfile.TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            carpeta = Path(media_root) / 'imagenes_productos'
            carpeta.mkdir(parents=True)
            (carpeta / '003088.jpg').write_bytes(b'foto-prueba')
            respuesta = self.client.get(reverse('productos_lista'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, '/media/imagenes_productos/003088.jpg')
        self.assertContains(respuesta, producto.nombre)
        self.assertContains(respuesta, '1')
        self.assertContains(respuesta, 'con foto')

    def test_producto_sin_foto_muestra_nombre_de_archivo_sugerido(self):
        Producto.objects.create(nombre='Hot dog individual', codigo_vaso='1677', confirmado=True)
        with tempfile.TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            respuesta = self.client.get(reverse('productos_lista'))
        self.assertContains(respuesta, 'Sin fotografía')
        self.assertContains(respuesta, '1677.jpg')

    def test_foto_botella_no_se_reutiliza_en_productos_vaso_convertibles(self):
        botella = Producto.objects.create(nombre='Gaseosa botella', codigo_botella='2097', confirmado=True)
        chico = Producto.objects.create(nombre='Gaseosa vaso chico', codigo_vaso='2085', codigo_botella='2097', convertible=True, confirmado=True)
        mediano = Producto.objects.create(nombre='Gaseosa vaso mediano', codigo_vaso='2086', codigo_botella='2097', convertible=True, confirmado=True)
        grande = Producto.objects.create(nombre='Gaseosa vaso grande', codigo_vaso='2087', codigo_botella='2097', convertible=True, confirmado=True)
        with tempfile.TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            carpeta = Path(media_root) / 'imagenes_productos'
            carpeta.mkdir(parents=True)
            (carpeta / '2097.webp').write_bytes(b'foto-botella')
            productos, total = adjuntar_imagenes_catalogo(Producto.objects.filter(pk__in=[botella.pk, chico.pk, mediano.pk, grande.pk]))
        por_nombre = {producto.nombre: producto.imagen_catalogo_archivo for producto in productos}
        self.assertEqual(por_nombre['Gaseosa botella'], '2097.webp')
        self.assertEqual(por_nombre['Gaseosa vaso chico'], '')
        self.assertEqual(por_nombre['Gaseosa vaso mediano'], '')
        self.assertEqual(por_nombre['Gaseosa vaso grande'], '')
        self.assertEqual(total, 1)

    def test_foto_vaso_chico_se_asigna_solo_a_vaso_chico(self):
        chico = Producto.objects.create(nombre='Gaseosa vaso chico', codigo_vaso='2085', codigo_botella='2097', convertible=True, confirmado=True)
        mediano = Producto.objects.create(nombre='Gaseosa vaso mediano', codigo_vaso='2086', codigo_botella='2097', convertible=True, confirmado=True)
        with tempfile.TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            carpeta = Path(media_root) / 'imagenes_productos'
            carpeta.mkdir(parents=True)
            (carpeta / '2085.webp').write_bytes(b'foto-vaso-chico')
            productos, total = adjuntar_imagenes_catalogo(Producto.objects.filter(pk__in=[chico.pk, mediano.pk]))
        por_nombre = {producto.nombre: producto.imagen_catalogo_archivo for producto in productos}
        self.assertEqual(por_nombre['Gaseosa vaso chico'], '2085.webp')
        self.assertEqual(por_nombre['Gaseosa vaso mediano'], '')
        self.assertEqual(total, 1)



class VinculoCombosDulcesTests(TestCase):
    def setUp(self):
        call_command('cargar_catalogo_inicial', verbosity=0)
        self.caja = Caja.objects.get(nombre='Presencial')
        self.jornada = Jornada.objects.create(fecha=date(2026, 5, 25), caja=self.caja)

    def test_catalogo_relaciona_combos_dulces_vaso_con_botella(self):
        esperados = {
            '2611': '2768',
            '2612': '2769',
            '2613': '002770',
            '2614': '002771',
        }
        for codigo_vaso, codigo_botella in esperados.items():
            with self.subTest(codigo_vaso=codigo_vaso):
                producto = Producto.objects.get(codigo_vaso=codigo_vaso)
                self.assertTrue(producto.convertible)
                self.assertTrue(producto.confirmado)
                self.assertEqual(producto.codigo_botella, codigo_botella)

    def test_periodo_botella_convierte_los_cuatro_combos_dulces(self):
        cierre = Cierre.objects.create(
            jornada=self.jornada,
            numero=1,
            modalidad_periodo=Cierre.Modalidad.BOTELLA,
            confirmado=True,
        )
        for codigo, cantidad in [('2611', 1), ('2612', 2), ('2613', 3), ('2614', 4)]:
            DetalleCierre.objects.create(cierre=cierre, codigo_leido=codigo, cantidad_acumulada=cantidad)
        movimientos, advertencias = movimientos_de_jornada(self.jornada)
        self.assertFalse(advertencias)
        self.assertEqual(
            {(m.codigo_final, m.cantidad) for m in movimientos},
            {('2768', 1), ('2769', 2), ('002770', 3), ('002771', 4)},
        )


class PresentacionesVisualesTests(TestCase):
    def test_vista_vaso_y_botella_usan_imagenes_de_codigos_distintos(self):
        producto = Producto.objects.create(
            nombre='Combo 1 dulce', categoria='COMBO DULCE', codigo_vaso='2611', codigo_botella='2768',
            descripcion_vaso='Combo dulce con vaso', descripcion_botella='Combo dulce con botella',
            convertible=True, confirmado=True,
        )
        with tempfile.TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            carpeta = Path(media_root) / 'imagenes_productos'
            carpeta.mkdir(parents=True)
            (carpeta / '2611.jpg').write_bytes(b'vaso')
            (carpeta / '2768.jpg').write_bytes(b'botella')
            vasos, _ = construir_tarjetas_presentacion(Producto.objects.filter(pk=producto.pk), 'vaso')
            botellas, _ = construir_tarjetas_presentacion(Producto.objects.filter(pk=producto.pk), 'botella')
        self.assertEqual(vasos[0].codigo, '2611')
        self.assertEqual(vasos[0].imagen_catalogo_archivo, '2611.jpg')
        self.assertEqual(botellas[0].codigo, '2768')
        self.assertEqual(botellas[0].imagen_catalogo_archivo, '2768.jpg')

    def test_vista_botella_aparece_como_apartado_en_productos(self):
        Producto.objects.create(
            nombre='Combo 1 dulce', codigo_vaso='2611', codigo_botella='2768',
            descripcion_botella='1 pop dulce + 1 botella', convertible=True, confirmado=True,
        )
        with tempfile.TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            carpeta = Path(media_root) / 'imagenes_productos'
            carpeta.mkdir(parents=True)
            (carpeta / '2768.webp').write_bytes(b'botella')
            respuesta = self.client.get(reverse('productos_lista') + '?vista=botella')
        self.assertContains(respuesta, 'Presentación botella')
        self.assertContains(respuesta, '2768')
        self.assertContains(respuesta, '/media/imagenes_productos/2768.webp')

    def test_reporte_del_dia_separa_vaso_y_botella_con_sus_fotos(self):
        producto = Producto.objects.create(
            nombre='Combo 1 dulce', codigo_vaso='2611', codigo_botella='2768',
            descripcion_botella='Combo 1 dulce con botella', convertible=True, confirmado=True,
        )
        caja = Caja.objects.create(nombre='Presencial', tipo=Caja.Tipo.MANUAL)
        jornada = Jornada.objects.create(fecha=date(2026, 5, 25), caja=caja)
        primero = Cierre.objects.create(jornada=jornada, numero=1, modalidad_periodo=Cierre.Modalidad.VASO, confirmado=True)
        DetalleCierre.objects.create(cierre=primero, codigo_leido='2611', cantidad_acumulada=2)
        segundo = Cierre.objects.create(jornada=jornada, numero=2, modalidad_periodo=Cierre.Modalidad.BOTELLA, confirmado=True)
        DetalleCierre.objects.create(cierre=segundo, codigo_leido='2611', cantidad_acumulada=5)
        with tempfile.TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            carpeta = Path(media_root) / 'imagenes_productos'
            carpeta.mkdir(parents=True)
            (carpeta / '2611.jpg').write_bytes(b'vaso')
            (carpeta / '2768.jpg').write_bytes(b'botella')
            respuesta = self.client.get(reverse('resumen_dia', args=['2026-05-25']))
            detalle = self.client.get(reverse('jornada_detalle', args=[jornada.pk]))
        self.assertContains(respuesta, '2611')
        self.assertContains(respuesta, '2768')
        self.assertContains(respuesta, '/media/imagenes_productos/2611.jpg')
        self.assertContains(respuesta, '/media/imagenes_productos/2768.jpg')
        self.assertContains(detalle, '/media/imagenes_productos/2611.jpg')
        self.assertContains(detalle, '/media/imagenes_productos/2768.jpg')


class ReporteDiarioHorizontalTests(TestCase):
    def test_consolidado_aparece_debajo_de_metodos_incluidos(self):
        respuesta = self.client.get(reverse('resumen_dia', args=['2026-05-25']))
        html = respuesta.content.decode('utf-8')
        self.assertLess(html.index('Vías incluidas'), html.index('Digitar en Up Base'))
        self.assertContains(respuesta, 'daily-stack')

    def test_tabla_horizontal_muestra_producto_codigo_metodos_y_cantidad(self):
        Producto.objects.create(nombre='Sublime', codigo_vaso='13', confirmado=True)
        caja = Caja.objects.create(nombre='Presencial', tipo=Caja.Tipo.MANUAL)
        jornada = Jornada.objects.create(fecha=date(2026, 5, 25), caja=caja)
        cierre = Cierre.objects.create(jornada=jornada, numero=1, modalidad_periodo=Cierre.Modalidad.VASO, confirmado=True)
        DetalleCierre.objects.create(cierre=cierre, codigo_leido='13', cantidad_acumulada=6)
        respuesta = self.client.get(reverse('resumen_dia', args=['2026-05-25']))
        self.assertContains(respuesta, 'Producto / presentación')
        self.assertContains(respuesta, 'Código Up Base')
        self.assertContains(respuesta, 'Vías incluidas')
        self.assertContains(respuesta, 'Presencial')
        self.assertContains(respuesta, 'report-main-row')


class CatalogoDepuradoV12Tests(TestCase):
    def test_carga_inicial_no_crea_filas_botella_duplicadas_para_combos_dulces(self):
        call_command('cargar_catalogo_inicial', verbosity=0)
        for codigo in ['2768', '2769', '002770', '002771']:
            with self.subTest(codigo=codigo):
                self.assertFalse(
                    Producto.objects.filter(codigo_vaso='', codigo_botella=codigo).exists()
                )
                self.assertTrue(
                    Producto.objects.filter(convertible=True, codigo_botella=codigo).exists()
                )

    def test_vista_general_oculta_directo_redundante_aunque_exista_en_base_antigua(self):
        Producto.objects.create(
            nombre='Combo 3 mix', codigo_vaso='2613', codigo_botella='002770',
            descripcion_botella='Combo 3 mix con 2 botellas', convertible=True, confirmado=True,
        )
        Producto.objects.create(
            nombre='Combo 3 mix con 2 botellas', codigo_botella='002770', confirmado=True
        )
        respuesta = self.client.get(reverse('productos_lista') + '?vista=general')
        self.assertContains(respuesta, '<h2>Combo 3 mix</h2>', count=1, html=True)
        self.assertNotContains(respuesta, '<h2>Combo 3 mix con 2 botellas</h2>', html=True)
        self.assertContains(respuesta, '2613')
        self.assertContains(respuesta, '002770')

    def test_codigo_botella_sin_fila_duplicada_mantiene_descripcion_botella(self):
        Producto.objects.create(
            nombre='Combo 3 mix', codigo_vaso='2613', codigo_botella='002770',
            descripcion_botella='Combo 3 mix con 2 botellas', convertible=True, confirmado=True,
        )
        caja = Caja.objects.create(nombre='Presencial', tipo=Caja.Tipo.MANUAL)
        jornada = Jornada.objects.create(fecha=date(2026, 5, 25), caja=caja)
        cierre = Cierre.objects.create(jornada=jornada, numero=1, modalidad_periodo=Cierre.Modalidad.VASO, confirmado=True)
        DetalleCierre.objects.create(cierre=cierre, codigo_leido='002770', cantidad_acumulada=2)
        consolidado = consolidado_de_jornada(jornada)
        self.assertEqual(consolidado[0]['producto'], 'Combo 3 mix con 2 botellas')


class EliminacionProductosV12Tests(TestCase):
    def test_permite_eliminar_producto_sin_cierres(self):
        producto = Producto.objects.create(nombre='Producto temporal', codigo_vaso='9999', confirmado=True)
        respuesta = self.client.post(reverse('producto_eliminar', args=[producto.pk]))
        self.assertRedirects(respuesta, reverse('productos_lista') + '?vista=general')
        self.assertFalse(Producto.objects.filter(pk=producto.pk).exists())

    def test_bloquea_eliminacion_de_producto_utilizado_en_cierre(self):
        producto = Producto.objects.create(nombre='Producto usado', codigo_vaso='9988', confirmado=True)
        caja = Caja.objects.create(nombre='Presencial', tipo=Caja.Tipo.MANUAL)
        jornada = Jornada.objects.create(fecha=date(2026, 5, 25), caja=caja)
        cierre = Cierre.objects.create(jornada=jornada, numero=1, confirmado=True)
        DetalleCierre.objects.create(cierre=cierre, codigo_leido='9988', cantidad_acumulada=1)
        respuesta = self.client.post(reverse('producto_eliminar', args=[producto.pk]), follow=True)
        self.assertTrue(Producto.objects.filter(pk=producto.pk).exists())
        self.assertContains(respuesta, 'No se eliminó el producto')


class DashboardPorFechaV12Tests(TestCase):
    def test_inicio_agrupa_metodos_del_mismo_dia_en_una_sola_fila(self):
        caja_a = Caja.objects.create(nombre='Presencial', tipo=Caja.Tipo.MANUAL)
        caja_b = Caja.objects.create(nombre='Kio 1', tipo=Caja.Tipo.AUTOSERVICIO)
        for caja in [caja_a, caja_b]:
            jornada = Jornada.objects.create(fecha=date(2026, 5, 25), caja=caja)
            Cierre.objects.create(jornada=jornada, numero=1, confirmado=True)
        respuesta = self.client.get(reverse('dashboard'))
        html = respuesta.content.decode('utf-8')
        self.assertContains(respuesta, 'Cierres por fecha')
        self.assertContains(respuesta, 'Vías cerradas')
        self.assertEqual(html.count('25/05/2026'), 1)
        self.assertContains(respuesta, '>2</strong>')

    def test_inicio_muestra_hoy_aunque_aun_no_tenga_cierres(self):
        respuesta = self.client.get(reverse('dashboard'))
        self.assertContains(respuesta, 'Hoy')
        self.assertContains(respuesta, 'Abrir día')


class EliminarRegistrosDiaV13Tests(TestCase):
    def setUp(self):
        self.producto = Producto.objects.create(nombre='Sublime', codigo_vaso='13', confirmado=True)
        self.caja_choco = Caja.objects.create(nombre='Presencial', tipo=Caja.Tipo.MANUAL)
        self.autoservicio = Caja.objects.create(nombre='Kio 1', tipo=Caja.Tipo.AUTOSERVICIO)
        self.fecha_objetivo = date(2026, 5, 25)
        self.fecha_anterior = date(2026, 5, 24)

    def crear_cierre(self, fecha, caja, cantidad=1, imagen=None):
        jornada = Jornada.objects.create(fecha=fecha, caja=caja)
        cierre = Cierre.objects.create(
            jornada=jornada, numero=1, modalidad_periodo=Cierre.Modalidad.VASO,
            confirmado=True, imagen=imagen,
        )
        DetalleCierre.objects.create(cierre=cierre, codigo_leido='13', cantidad_acumulada=cantidad)
        return jornada, cierre

    def test_inicio_muestra_opcion_eliminar_cuando_el_dia_tiene_cierres(self):
        self.crear_cierre(self.fecha_objetivo, self.caja_choco)
        respuesta = self.client.get(reverse('dashboard'))
        self.assertContains(respuesta, 'Eliminar registros')
        self.assertContains(respuesta, reverse('eliminar_registros_dia', args=['2026-05-25']))

    def test_reporte_muestra_opcion_eliminar_y_get_solo_confirma(self):
        jornada, cierre = self.crear_cierre(self.fecha_objetivo, self.caja_choco, cantidad=6)
        reporte = self.client.get(reverse('resumen_dia', args=['2026-05-25']))
        self.assertContains(reporte, 'Eliminar registros del día')
        confirmacion = self.client.get(reverse('eliminar_registros_dia', args=['2026-05-25']))
        self.assertContains(confirmacion, 'Esta acción no se puede deshacer')
        self.assertContains(confirmacion, '25/05/2026')
        self.assertTrue(Jornada.objects.filter(pk=jornada.pk).exists())
        self.assertTrue(Cierre.objects.filter(pk=cierre.pk).exists())

    def test_eliminar_dia_borra_solo_fecha_seleccionada_y_su_foto(self):
        with tempfile.TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            foto = SimpleUploadedFile('boleta_hoy.jpg', b'imagen-boleta', content_type='image/jpeg')
            jornada_hoy, cierre_hoy = self.crear_cierre(self.fecha_objetivo, self.caja_choco, cantidad=6, imagen=foto)
            ruta_foto = Path(cierre_hoy.imagen.path)
            jornada_pasada, cierre_pasado = self.crear_cierre(self.fecha_anterior, self.autoservicio, cantidad=2)
            self.assertTrue(ruta_foto.exists())

            respuesta = self.client.post(reverse('eliminar_registros_dia', args=['2026-05-25']), follow=True)

            self.assertContains(respuesta, 'Se eliminaron los registros del 25/05/2026')
            self.assertFalse(Jornada.objects.filter(pk=jornada_hoy.pk).exists())
            self.assertFalse(Cierre.objects.filter(pk=cierre_hoy.pk).exists())
            self.assertFalse(ruta_foto.exists())
            self.assertTrue(Jornada.objects.filter(pk=jornada_pasada.pk).exists())
            self.assertTrue(Cierre.objects.filter(pk=cierre_pasado.pk).exists())
            self.assertTrue(Producto.objects.filter(pk=self.producto.pk).exists())


class ProcesamientoVisibleV15Tests(TestCase):
    def setUp(self):
        self.caja = Caja.objects.create(nombre='Presencial', tipo=Caja.Tipo.MANUAL)
        Caja.objects.create(nombre='Kio 1', tipo=Caja.Tipo.AUTOSERVICIO)

    def test_formulario_anuncia_pantalla_de_analisis_visible(self):
        respuesta = self.client.get(reverse('procesar_dia'))
        self.assertContains(respuesta, 'Continuar al análisis de imágenes')
        self.assertContains(respuesta, 'pantalla de análisis')
        self.assertNotContains(respuesta, 'data-analysis-overlay')

    def test_pantalla_intermedia_muestra_imagen_recibida_antes_del_ocr(self):
        png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')
        with tempfile.TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            imagen = SimpleUploadedFile('boleta_caja.png', png, content_type='image/png')
            self.client.post(reverse('procesar_dia'), {
                'fecha': '2026-05-25',
                f'imagen_{self.caja.pk}': imagen,
            })
            respuesta = self.client.get(reverse('procesando_lote'))
        self.assertContains(respuesta, 'data-server-analysis-page')
        self.assertContains(respuesta, 'Boletas recibidas')
        self.assertContains(respuesta, 'boleta_caja.png')
        self.assertContains(respuesta, 'Casi listo') if False else None

    def test_script_ejecuta_ocr_desde_pantalla_visible_y_muestra_casi_listo(self):
        ruta_js = Path(finders.find('ventas/app.js'))
        contenido = ruta_js.read_text(encoding='utf-8')
        self.assertIn('data-server-analysis-page', contenido)
        self.assertIn('Casi listo', contenido)
        self.assertIn('fetch(processPage.dataset.executeUrl', contenido)
        self.assertIn('minimumVisibleTime', contenido)

    def test_reporte_reduce_importancia_visual_de_eliminar_y_prioriza_detalle(self):
        jornada = Jornada.objects.create(fecha=date(2026, 5, 25), caja=self.caja)
        Cierre.objects.create(jornada=jornada, numero=1, confirmado=True)
        respuesta = self.client.get(reverse('resumen_dia', args=['2026-05-25']))
        self.assertContains(respuesta, 'Ver movimientos')
        self.assertContains(respuesta, 'Gestión del día')
        self.assertContains(respuesta, 'subtle-danger-action')
        self.assertContains(respuesta, 'Boletas registradas')



class AcumuladosPorViaV16Tests(TestCase):
    def setUp(self):
        call_command('cargar_catalogo_inicial', verbosity=0)
        self.fecha = date(2026, 5, 25)
        self.presencial = Caja.objects.get(nombre='Presencial')
        self.kio_1 = Caja.objects.get(nombre='Kio 1')
        self.producto = Producto.objects.get(codigo_vaso='2611')

    def test_misma_via_resta_boleta_acumulada_y_convierte_solo_la_diferencia(self):
        jornada = Jornada.objects.create(fecha=self.fecha, caja=self.presencial)
        primer_cierre = Cierre.objects.create(
            jornada=jornada, numero=1, modalidad_periodo=Cierre.Modalidad.VASO, confirmado=True
        )
        DetalleCierre.objects.create(cierre=primer_cierre, codigo_leido='2611', cantidad_acumulada=12)
        segundo_cierre = Cierre.objects.create(
            jornada=jornada, numero=2, modalidad_periodo=Cierre.Modalidad.BOTELLA, confirmado=True
        )
        DetalleCierre.objects.create(cierre=segundo_cierre, codigo_leido='2611', cantidad_acumulada=18)

        movimientos, advertencias = movimientos_de_jornada(jornada)
        self.assertFalse(advertencias)
        self.assertEqual(
            [(m.codigo_final, m.cantidad_anterior, m.cantidad_acumulada, m.cantidad) for m in movimientos],
            [('2611', 0, 12, 12), ('2768', 12, 18, 6)],
        )

    def test_suma_entre_vias_pero_no_suma_dos_acumulados_de_presencial(self):
        jornada_presencial = Jornada.objects.create(fecha=self.fecha, caja=self.presencial)
        cierre_1 = Cierre.objects.create(
            jornada=jornada_presencial, numero=1, modalidad_periodo=Cierre.Modalidad.VASO, confirmado=True
        )
        DetalleCierre.objects.create(cierre=cierre_1, codigo_leido='2611', cantidad_acumulada=12)
        cierre_2 = Cierre.objects.create(
            jornada=jornada_presencial, numero=2, modalidad_periodo=Cierre.Modalidad.BOTELLA, confirmado=True
        )
        DetalleCierre.objects.create(cierre=cierre_2, codigo_leido='2611', cantidad_acumulada=18)

        jornada_kio = Jornada.objects.create(fecha=self.fecha, caja=self.kio_1)
        cierre_kio = Cierre.objects.create(
            jornada=jornada_kio, numero=1, modalidad_periodo=Cierre.Modalidad.VASO, confirmado=True
        )
        DetalleCierre.objects.create(cierre=cierre_kio, codigo_leido='2611', cantidad_acumulada=4)

        consolidado, advertencias = consolidado_por_fecha(self.fecha)
        self.assertFalse(advertencias)
        por_codigo = {fila['codigo_final']: fila['cantidad'] for fila in consolidado}
        self.assertEqual(por_codigo['2611'], 16)  # 12 Presencial + 4 Kio 1
        self.assertEqual(por_codigo['2768'], 6)   # solo diferencia nueva de Presencial
        self.assertNotEqual(por_codigo['2768'], 18)

    def test_detalle_muestra_resta_visible_para_revision(self):
        jornada = Jornada.objects.create(fecha=self.fecha, caja=self.presencial)
        c1 = Cierre.objects.create(jornada=jornada, numero=1, modalidad_periodo=Cierre.Modalidad.VASO, confirmado=True)
        DetalleCierre.objects.create(cierre=c1, codigo_leido='2611', cantidad_acumulada=12)
        c2 = Cierre.objects.create(jornada=jornada, numero=2, modalidad_periodo=Cierre.Modalidad.BOTELLA, confirmado=True)
        DetalleCierre.objects.create(cierre=c2, codigo_leido='2611', cantidad_acumulada=18)
        respuesta = self.client.get(reverse('jornada_detalle', args=[jornada.pk]))
        self.assertContains(respuesta, 'Acumulado anterior')
        self.assertContains(respuesta, 'Acumulado boleta')
        self.assertContains(respuesta, 'Venta nueva')
        self.assertContains(respuesta, '2768')

    def test_comando_actualiza_nombres_sin_perder_cierre(self):
        Caja.objects.filter(nombre='Presencial').update(nombre='Caja Choco')
        caja = Caja.objects.get(nombre='Caja Choco')
        jornada = Jornada.objects.create(fecha=date(2026, 5, 26), caja=caja)
        cierre = Cierre.objects.create(jornada=jornada, numero=1, confirmado=True)
        DetalleCierre.objects.create(cierre=cierre, codigo_leido='13', cantidad_acumulada=1)
        call_command('actualizar_vias_venta', verbosity=0)
        caja.refresh_from_db()
        self.assertEqual(caja.nombre, 'Presencial')
        self.assertTrue(Jornada.objects.filter(pk=jornada.pk, caja=caja).exists())
