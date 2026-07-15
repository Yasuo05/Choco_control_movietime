from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re
from statistics import median
from typing import Iterable, Sequence

from django.conf import settings


FILAS_MARKER = '=== FILAS DETECTADAS PARA REVISIÓN ==='
TEXTO_MARKER = '=== TEXTO OCR COMPLETO ==='


@dataclass
class FilaOCR:
    codigo: str
    descripcion: str
    cantidad: int | None
    confianza_descripcion: float = 0.0
    confianza_cantidad: float | None = None
    alerta: str = ''

    def serializar(self) -> str:
        cantidad = '?' if self.cantidad is None else str(self.cantidad)
        descripcion = self.descripcion.replace('\t', ' ').strip()
        alerta = self.alerta.replace('\t', ' ').strip()
        return f'{self.codigo}\t{cantidad}\t{descripcion}\t{alerta}'


@dataclass
class CajaTextoOCR:
    texto: str
    box: Sequence[Sequence[float]]
    confianza: float

    @property
    def centro_x(self) -> float:
        return sum(p[0] for p in self.box) / len(self.box)

    @property
    def centro_y(self) -> float:
        return sum(p[1] for p in self.box) / len(self.box)

    @property
    def min_x(self) -> float:
        return min(p[0] for p in self.box)


def _solo_digitos_iniciales(texto: str) -> str:
    texto = texto.strip().upper()
    coincidencia = re.match(r'^([0-9OIL]{1,8})', texto)
    if not coincidencia:
        return ''
    return coincidencia.group(1).replace('O', '0').replace('I', '1').replace('L', '1')


def _clave(codigo: str) -> str:
    return codigo.lstrip('0') or '0'


def _variantes_cero_ocho(token: str) -> set[str]:
    """Genera variantes probables cuando el OCR confunde 0 y 8.

    En las boletas térmicas el cero suele cerrarse y RapidOCR a veces lo lee
    como 8. Se limita la expansión a códigos cortos para no crear demasiados
    falsos positivos.
    """
    token = str(token or '')
    posiciones = [i for i, ch in enumerate(token) if ch in {'0', '8'}]
    if not posiciones or len(posiciones) > 4:
        return {token}
    variantes = {token}
    for mascara in range(1, 1 << len(posiciones)):
        chars = list(token)
        for bit, pos in enumerate(posiciones):
            if mascara & (1 << bit):
                chars[pos] = '0' if chars[pos] == '8' else '8'
        variantes.add(''.join(chars))
    return variantes


def _distancia_codigo_ocr(a: str, b: str) -> float:
    """Distancia tolerante para corregir códigos OCR contra catálogo.

    La confusión 0<->8 tiene menor costo; una diferencia de ceros iniciales no
    penaliza. Otros cambios sí penalizan más para no convertir códigos nuevos
    en productos existentes por error.
    """
    a = str(a or '').rjust(max(len(a), len(b)), '0')
    b = str(b or '').rjust(max(len(a), len(b)), '0')
    costo = 0.0
    for x, y in zip(a, b):
        if x == y:
            continue
        if {x, y} == {'0', '8'}:
            costo += 0.28
        else:
            costo += 1.0
    return costo


def _corregir_codigo_probable(token: str, codigos_catalogo: Iterable[str]) -> tuple[str, str]:
    """Devuelve código corregido y alerta si aplica.

    Ejemplo real: 2085 puede verse como 2885. Si existe 2085 en catálogo y
    2885 no existe, se corrige automáticamente y se marca para revisión.
    """
    token_sin_ceros = _clave(token)
    conocidos = {_clave(c) for c in codigos_catalogo if c}
    if token_sin_ceros in conocidos:
        return token_sin_ceros, ''

    # Primero prueba variantes explícitas 0/8. Esto cubre casos como
    # 2885 -> 2085, 2886 -> 2086 y 8009 -> 9.
    candidatos = []
    for variante in _variantes_cero_ocho(token):
        clave_variante = _clave(variante)
        if clave_variante in conocidos:
            candidatos.append((clave_variante, _distancia_codigo_ocr(token_sin_ceros, clave_variante)))
    if candidatos:
        codigo, _ = min(candidatos, key=lambda item: (item[1], len(item[0])))
        return codigo, f'Código leído como {token_sin_ceros}; se corrigió a {codigo} por posible confusión entre 0 y 8. Revise visualmente.'

    # Respaldo: busca un código del mismo tamaño o con ceros iniciales cuya
    # única diferencia importante sea 0/8. No corrige si hay empate.
    posibles = []
    for conocido in conocidos:
        if abs(len(conocido) - len(token_sin_ceros)) > 2:
            continue
        distancia = _distancia_codigo_ocr(token_sin_ceros, conocido)
        if distancia <= 0.60:
            posibles.append((conocido, distancia))
    posibles.sort(key=lambda item: (item[1], len(item[0])))
    if len(posibles) == 1 or (len(posibles) > 1 and posibles[0][1] < posibles[1][1]):
        codigo = posibles[0][0]
        return codigo, f'Código leído como {token_sin_ceros}; se sugirió {codigo} por similitud OCR. Revise visualmente.'
    return token_sin_ceros, ''


def extraer_codigo_descripcion_con_alerta(texto: str, codigos_catalogo: Iterable[str]) -> tuple[str, str]:
    """Obtiene el código impreso al inicio de una fila y corrige 0/8.

    Los códigos pueden venir con ceros a la izquierda (0004 -> 4). Cuando el
    OCR pega el inicio de la descripción al código (por ejemplo 25121POP), se
    permite recortar únicamente hacia un código conocido de tres o más dígitos.
    Esta regla evita interpretar códigos nuevos como 4171/4177/4181 como el
    producto 4 (Travesuras).
    """
    token = _solo_digitos_iniciales(texto)
    if not token:
        return '', ''
    conocidos = sorted({_clave(c) for c in codigos_catalogo if c}, key=len, reverse=True)
    token_sin_ceros = _clave(token)
    codigo_corregido, alerta = _corregir_codigo_probable(token, conocidos)
    if codigo_corregido in conocidos:
        return codigo_corregido, alerta
    if len(token_sin_ceros) <= 4:
        return token_sin_ceros, alerta
    for codigo in conocidos:
        if len(codigo) >= 3 and token_sin_ceros.startswith(codigo):
            return codigo, ''
        # Variante adicional cuando el token pegado a la descripción trae 0/8
        # confundido al inicio: 2885GASEOSA -> 2085.
        if len(codigo) >= 3 and _distancia_codigo_ocr(token_sin_ceros[:len(codigo)], codigo) <= 0.60:
            return codigo, f'Código leído como {token_sin_ceros[:len(codigo)]}; se corrigió a {codigo} por posible confusión entre 0 y 8. Revise visualmente.'
    return token_sin_ceros, alerta


def extraer_codigo_descripcion(texto: str, codigos_catalogo: Iterable[str]) -> str:
    codigo, _ = extraer_codigo_descripcion_con_alerta(texto, codigos_catalogo)
    return codigo


def _normalizar_ocr(texto: str) -> str:
    return str(texto or '').upper().replace('0', 'O').replace('Í', 'I')


def _recortar_seccion_productos(cajas: list[CajaTextoOCR]) -> list[CajaTextoOCR]:
    """Ignora encabezados previos como ventas por forma de pago.

    La boleta puede contener varias tablas con columnas Cant./P.Total. Para no
    mezclar pagos con productos se procesa, cuando está visible, solo el bloque
    situado debajo de ``Detalle de productos``.
    """
    marcadores = [
        caja for caja in cajas
        if 'DETALLE' in _normalizar_ocr(caja.texto)
        and 'PRODUCT' in _normalizar_ocr(caja.texto)
    ]
    if not marcadores:
        return cajas
    inicio = max(marcadores, key=lambda caja: caja.centro_y).centro_y
    return [caja for caja in cajas if caja.centro_y > inicio + 2]


def _ajuste_lineal(pares: list[tuple[float, float]]) -> tuple[float, float]:
    if len(pares) < 2:
        return 1.0, 0.0
    n = float(len(pares))
    sx = sum(x for x, _ in pares)
    sy = sum(y for _, y in pares)
    sxx = sum(x * x for x, _ in pares)
    sxy = sum(x * y for x, y in pares)
    denominador = n * sxx - sx * sx
    if abs(denominador) < 1e-6:
        return 1.0, (sy - sx) / n
    pendiente = (n * sxy - sx * sy) / denominador
    intercepto = (sy - pendiente * sx) / n
    return pendiente, intercepto


def _asignar_segun_modelo(
    descripciones: list[tuple[CajaTextoOCR, str]], cantidades: list[CajaTextoOCR],
    pendiente: float, intercepto: float, tolerancia: float,
) -> tuple[dict[int, tuple[int, CajaTextoOCR]], float]:
    usados: set[int] = set()
    asignados: dict[int, tuple[int, CajaTextoOCR]] = {}
    error_total = 0.0
    for posicion, (descripcion, _) in enumerate(descripciones):
        prediccion = pendiente * descripcion.centro_y + intercepto
        candidatos = [
            (indice, cantidad) for indice, cantidad in enumerate(cantidades)
            if indice not in usados and abs(cantidad.centro_y - prediccion) <= tolerancia
        ]
        if not candidatos:
            continue
        indice, cantidad = min(candidatos, key=lambda par: abs(par[1].centro_y - prediccion))
        usados.add(indice)
        asignados[posicion] = (indice, cantidad)
        error_total += abs(cantidad.centro_y - prediccion)
    return asignados, error_total


def _cantidades_por_perspectiva(
    descripciones: list[tuple[CajaTextoOCR, str]], cantidades: list[CajaTextoOCR]
) -> dict[int, tuple[int, CajaTextoOCR]]:
    """Relaciona filas y cantidades para una boleta inclinada.

    Se calibra progresivamente con las últimas filas ya asociadas, porque la
    separación vertical cambia hacia la parte baja del papel por la perspectiva.
    Si una cifra no aparece, la fila queda para revisión y la siguiente cantidad
    no se desplaza a un producto equivocado.
    """
    if not descripciones or not cantidades:
        return {}
    distancias = [
        descripciones[i + 1][0].centro_y - descripciones[i][0].centro_y
        for i in range(len(descripciones) - 1)
    ]
    tolerancia = max(9.0, min(15.0, median(distancias) * 0.46 if distancias else 11.0))
    asignados: dict[int, tuple[int, CajaTextoOCR]] = {}
    usados: set[int] = set()
    pares_confirmados: list[tuple[float, float]] = []
    for posicion, (descripcion, _) in enumerate(descripciones):
        if len(pares_confirmados) >= 3:
            pendiente, intercepto = _ajuste_lineal(pares_confirmados[-6:])
            prediccion = pendiente * descripcion.centro_y + intercepto
        elif posicion < len(cantidades):
            prediccion = cantidades[posicion].centro_y
        else:
            continue
        candidatos = [
            (indice, cantidad) for indice, cantidad in enumerate(cantidades)
            if indice not in usados and abs(cantidad.centro_y - prediccion) <= tolerancia
        ]
        if not candidatos:
            continue
        indice, cantidad = min(candidatos, key=lambda par: abs(par[1].centro_y - prediccion))
        usados.add(indice)
        asignados[posicion] = (indice, cantidad)
        pares_confirmados.append((descripcion.centro_y, cantidad.centro_y))
    return asignados



def _detectar_uno_en_columna(imagen, descripcion: CajaTextoOCR, cantidades: list[CajaTextoOCR]) -> tuple[int | None, str]:
    """Refuerzo visual para el dígito 1 en la columna Cant.

    En la parte baja de las boletas térmicas el OCR suele perder los unos
    porque son trazos muy delgados y el papel queda oscuro/inclinado. Esta
    lectura no reemplaza una cantidad detectada; solo se usa cuando la fila ya
    quedó sin cantidad y existen otras cantidades que permiten ubicar la columna.
    """
    if imagen is None or not cantidades:
        return None, ''
    try:
        import cv2
        import numpy as np

        alto, ancho_img = imagen.shape[:2]
        x_centro = int(median([c.centro_x for c in cantidades]))
        y_centro = int(descripcion.centro_y)
        # La columna de cantidad es angosta; un crop pequeño evita leer el precio.
        x1, x2 = max(0, x_centro - 22), min(ancho_img, x_centro + 24)
        y1, y2 = max(0, y_centro - 13), min(alto, y_centro + 14)
        if x2 <= x1 or y2 <= y1:
            return None, ''
        crop = imagen[y1:y2, x1:x2]
        gris = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        gris = cv2.GaussianBlur(gris, (3, 3), 0)
        # Binarización local: texto oscuro sobre papel claro/gris.
        binaria = cv2.adaptiveThreshold(
            gris, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 7
        )
        # Retira líneas horizontales finas de la boleta si atraviesan el crop.
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (12, 1))
        horizontales = cv2.morphologyEx(binaria, cv2.MORPH_OPEN, horizontal_kernel)
        binaria = cv2.subtract(binaria, horizontales)
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binaria, 8)
        componentes = []
        for label in range(1, num_labels):
            x, y, w, h, area = stats[label]
            if area < 5 or h < 7:
                continue
            if w <= 9 and h / max(w, 1) >= 1.7:
                componentes.append((x, y, w, h, area))
        if componentes:
            # Si hay un trazo vertical delgado en la zona de cantidad, lo más
            # probable en estas boletas es un 1. Se marca para revisión visual.
            return 1, 'Cantidad 1 detectada por refuerzo visual en la columna Cant.; verifique esta fila.'

        # Respaldo: intenta OCR solo sobre la celda ampliada, pero sin confiar si
        # devuelve valores distintos de 1.
        ampliada = cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        # No se usa el motor principal aquí para evitar recursiones y costo alto.
        return None, ''
    except Exception:
        return None, ''


def extraer_filas(resultados: Sequence, codigos_catalogo: Iterable[str], imagen=None, motor=None, alinear_por_orden: bool = False, detectar_resaltado: bool = True) -> list[FilaOCR]:
    """Convierte la salida OCR posicionada de una boleta en filas código/cantidad.

    El formato real de la boleta tiene tres columnas: Descripción, Cant. y P.Total.
    Solo se toman el código inicial y la columna Cant.; la columna monetaria se descarta.
    """
    cajas: list[CajaTextoOCR] = []
    for resultado in resultados or []:
        try:
            box, texto, confianza = resultado[0], str(resultado[1]), float(resultado[2])
        except (IndexError, TypeError, ValueError):
            continue
        cajas.append(CajaTextoOCR(texto=texto, box=box, confianza=confianza))

    if not cajas:
        return []

    cajas = _recortar_seccion_productos(cajas)
    if not cajas:
        return []
    ancho = max(max(p[0] for p in caja.box) for caja in cajas)
    encabezados = [c for c in cajas if re.search(r'\bCANT\b', c.texto.upper())]
    encabezado_cantidad = min(encabezados, key=lambda c: c.centro_y) if encabezados else None
    minimo_x_cantidad = (encabezado_cantidad.centro_x - max(ancho * 0.16, 45.0)) if encabezado_cantidad else ancho * 0.40

    codigos_catalogo = list(codigos_catalogo)
    descripciones: list[tuple[CajaTextoOCR, str]] = []
    cantidades: list[CajaTextoOCR] = []
    for caja in cajas:
        codigo, alerta_codigo = extraer_codigo_descripcion_con_alerta(caja.texto, codigos_catalogo)
        if codigo and caja.min_x < minimo_x_cantidad:
            # Guardamos la alerta en el texto auxiliar para no perderla al ordenar.
            caja.alerta_codigo = alerta_codigo
            descripciones.append((caja, codigo))
        # La boleta fotografiada puede quedar en perspectiva: la columna Cant.
        # se desplaza hacia la derecha a medida que baja el papel. Por eso no
        # exigimos un centro X fijo; usamos el primer número entero a la derecha.
        if caja.centro_x >= minimo_x_cantidad and re.fullmatch(r'\d{1,5}', caja.texto.strip()):
            cantidades.append(caja)

    filas: list[FilaOCR] = []
    descripciones = sorted(descripciones, key=lambda item: item[0].centro_y)
    cantidades = sorted(cantidades, key=lambda item: item.centro_y)
    cantidades_utilizadas: set[int] = set()
    asignadas_perspectiva = _cantidades_por_perspectiva(descripciones, cantidades) if alinear_por_orden else {}
    for posicion, (descripcion, codigo) in enumerate(descripciones):
        tolerancia_vertical = max(24.0, ancho * 0.032)
        cantidad_seleccionada = None
        indice_seleccionado = None
        if posicion in asignadas_perspectiva:
            indice_seleccionado, cantidad_seleccionada = asignadas_perspectiva[posicion]
        elif not alinear_por_orden:
            candidatos = [
                (indice, cantidad)
                for indice, cantidad in enumerate(cantidades)
                if indice not in cantidades_utilizadas
                and cantidad.centro_x > descripcion.min_x
                and abs(cantidad.centro_y - descripcion.centro_y) <= tolerancia_vertical
            ]
            if candidatos:
                indice_seleccionado, cantidad_seleccionada = min(
                    candidatos, key=lambda par: abs(par[1].centro_y - descripcion.centro_y)
                )
        if indice_seleccionado is not None:
            cantidades_utilizadas.add(indice_seleccionado)

        alerta = getattr(descripcion, 'alerta_codigo', '') or ''
        cantidad_numero: int | None = None
        confianza_cantidad: float | None = None
        if cantidad_seleccionada is None:
            cantidad_refuerzo, aviso_refuerzo = _detectar_uno_en_columna(imagen, descripcion, cantidades)
            if cantidad_refuerzo is not None:
                cantidad_numero = cantidad_refuerzo
                confianza_cantidad = 0.72
                alerta = f'{alerta} {aviso_refuerzo}'.strip() if alerta else aviso_refuerzo
            else:
                aviso = 'Cantidad no detectada; complete esta fila mirando la boleta.'
                alerta = f'{alerta} {aviso}'.strip() if alerta else aviso
        else:
            cantidad_numero = int(cantidad_seleccionada.texto.strip())
            confianza_cantidad = cantidad_seleccionada.confianza
            if min(descripcion.confianza, cantidad_seleccionada.confianza) < 0.88:
                aviso = 'Lectura de baja confianza; verifique esta cantidad.'
                alerta = f'{alerta} {aviso}'.strip() if alerta else aviso

        if imagen is not None and detectar_resaltado:
            try:
                import cv2
                import numpy as np
                hsv = cv2.cvtColor(imagen, cv2.COLOR_BGR2HSV)
                y = int(descripcion.centro_y)
                banda = hsv[max(0, y - 13):min(hsv.shape[0], y + 13), :int(ancho)]
                amarillos = (
                    (banda[:, :, 0] >= 18) & (banda[:, :, 0] <= 45)
                    & (banda[:, :, 1] >= 45) & (banda[:, :, 2] >= 80)
                )
                if banda.size and float(np.mean(amarillos)) > 0.05:
                    aviso_resaltado = 'Fila resaltada en la foto; confirme la cantidad manualmente.'
                    alerta = f'{alerta} {aviso_resaltado}'.strip() if alerta else aviso_resaltado
                    # Una marca de resaltador puede alterar el número detectado.
                    # Por seguridad no se confirma automáticamente esa cantidad:
                    # se conserva la fila y se solicita verificarla en pantalla.
                    cantidad_numero = None
                    confianza_cantidad = None
            except Exception:
                pass

        filas.append(
            FilaOCR(
                codigo=codigo,
                descripcion=descripcion.texto,
                cantidad=cantidad_numero,
                confianza_descripcion=descripcion.confianza,
                confianza_cantidad=confianza_cantidad,
                alerta=alerta,
            )
        )
    return filas


def serializar_lectura(filas: list[FilaOCR], textos: Sequence[str]) -> str:
    lineas = [FILAS_MARKER]
    lineas.extend(fila.serializar() for fila in filas)
    lineas.append(TEXTO_MARKER)
    lineas.extend(str(texto) for texto in textos)
    return '\n'.join(lineas)


def leer_filas_serializadas(texto_ocr: str) -> list[FilaOCR]:
    filas: list[FilaOCR] = []
    en_filas = False
    for linea in (texto_ocr or '').splitlines():
        if linea.strip() == FILAS_MARKER:
            en_filas = True
            continue
        if linea.strip() == TEXTO_MARKER:
            break
        if not en_filas or not linea.strip():
            continue
        partes = linea.split('\t', 3)
        if len(partes) < 3:
            continue
        codigo, cantidad, descripcion = partes[:3]
        alerta = partes[3] if len(partes) > 3 else ''
        try:
            cantidad_numero = None if cantidad == '?' else int(cantidad)
        except ValueError:
            cantidad_numero = None
        filas.append(FilaOCR(codigo=codigo, cantidad=cantidad_numero, descripcion=descripcion, alerta=alerta))
    return filas


@lru_cache(maxsize=1)
def _motor_ocr():
    from rapidocr import RapidOCR

    modelos = Path(settings.BASE_DIR) / 'ocr_models'
    archivos = {
        'Det.model_path': modelos / 'ch_PP-OCRv4_det_infer.onnx',
        'Cls.model_path': modelos / 'ch_ppocr_mobile_v2.0_cls_infer.onnx',
        'Rec.model_path': modelos / 'ch_PP-OCRv4_rec_infer.onnx',
    }
    faltantes = [str(ruta.name) for ruta in archivos.values() if not ruta.exists()]
    if faltantes:
        raise FileNotFoundError(f'Faltan modelos OCR internos: {", ".join(faltantes)}')
    parametros = {
        'Global.model_root_dir': str(modelos),
        'Global.log_level': 'error',
        **{clave: str(ruta) for clave, ruta in archivos.items()},
    }
    return RapidOCR(params=parametros)


def _resultado_a_cajas(resultado) -> list[list]:
    if getattr(resultado, 'txts', None) is None or getattr(resultado, 'boxes', None) is None:
        return []
    return [
        [box, texto, puntaje]
        for box, texto, puntaje in zip(resultado.boxes, resultado.txts, resultado.scores)
    ]


def _recorte_central_boleta(imagen):
    """Recorta una boleta larga fotografiada sobre un fondo visible.

    En fotografías limpias la boleta ocupa una franja central del encuadre y el
    OCR sobre la escena completa puede detectar solo el fondo. Este recorte no
    depende de líneas impresas ni de resaltadores; conserva la sección central
    donde está la tabla de productos.
    """
    alto, ancho = imagen.shape[:2]
    x1, x2 = int(ancho * 0.20), int(ancho * 0.82)
    y1, y2 = int(alto * 0.18), int(alto * 0.97)
    return imagen[y1:y2, x1:x2]


def _boleta_con_fondo_visible(imagen) -> bool:
    """Detecta fotografías donde el papel no llena la imagen.

    El fondo de las fotos enviadas es intensamente coloreado, mientras la
    boleta es neutra. Si el fondo ocupa una fracción importante, se recorta la
    banda central antes del OCR para evitar que el detector se distraiga.
    """
    try:
        import cv2
        import numpy as np
        hsv = cv2.cvtColor(imagen, cv2.COLOR_BGR2HSV)
        papel = (hsv[:, :, 1] < 55) & (hsv[:, :, 2] > 75)
        return float(np.mean(papel)) < 0.72
    except Exception:
        return False


def ejecutar_ocr_embebido(ruta_imagen: str | Path, codigos_catalogo: Iterable[str]) -> tuple[str, str]:
    try:
        motor = _motor_ocr()
    except ImportError:
        return '', 'OCR interno no disponible: ejecute nuevamente pip install -r requirements.txt.'
    except Exception as exc:
        return '', f'No se pudo iniciar el OCR interno: {exc}'

    try:
        import cv2
        imagen_original = cv2.imread(str(ruta_imagen))
        if imagen_original is None:
            return '', 'No se pudo abrir la fotografía. Seleccione nuevamente la imagen.'

        imagen_recortada = _recorte_central_boleta(imagen_original)
        fondo_visible = _boleta_con_fondo_visible(imagen_original)
        intentos = (
            [('recorte', imagen_recortada, True), ('completa', imagen_original, False)]
            if fondo_visible
            else [('completa', imagen_original, False), ('recorte', imagen_recortada, True)]
        )
        mejor_filas: list[FilaOCR] = []
        mejores_textos: list[str] = []
        uso_recorte = False
        for nombre_intento, imagen_intento, ordenar in intentos:
            resultado = motor(imagen_intento)
            filas_intento = extraer_filas(
                _resultado_a_cajas(resultado), codigos_catalogo, imagen=imagen_intento, motor=motor,
                alinear_por_orden=ordenar, detectar_resaltado=not ordenar,
            )
            textos_intento = list(getattr(resultado, 'txts', None)) if getattr(resultado, 'txts', None) is not None else []
            puntaje = sum(1 for fila in filas_intento if fila.cantidad is not None) * 3 + len(filas_intento)
            mejor_puntaje = sum(1 for fila in mejor_filas if fila.cantidad is not None) * 3 + len(mejor_filas)
            if puntaje > mejor_puntaje:
                mejor_filas, mejores_textos = filas_intento, textos_intento
                uso_recorte = nombre_intento == 'recorte'
            # Si el papel ya llena la imagen y existe un bloque amplio de productos,
            # no se ejecuta otro recorte. En fotos con fondo, el recorte central
            # es el intento preferido y se acepta aunque unas pocas cifras queden
            # pendientes para revisión manual.
            completas = sum(1 for fila in filas_intento if fila.cantidad is not None)
            if (not fondo_visible and len(filas_intento) >= 10) or (
                fondo_visible and len(filas_intento) >= 20 and completas >= len(filas_intento) - 4
            ):
                break
        filas, textos = mejor_filas, mejores_textos
        texto_guardado = serializar_lectura(filas, textos)
        detectadas = sum(1 for fila in filas if fila.cantidad is not None)
        incompletas = sum(1 for fila in filas if fila.cantidad is None)
        if not filas:
            return texto_guardado, 'La imagen se analizó, pero no se identificaron filas. Ingrese códigos manualmente.'
        estado = f'OCR interno ejecutado: {len(filas)} producto(s) localizado(s); {detectadas} con cantidad.'
        if uso_recorte:
            estado += ' Boleta detectada mediante recorte automático del fondo.'
        if incompletas:
            estado += f' {incompletas} fila(s) necesitan completar la cantidad.'
        estado += ' Revise antes de guardar.'
        return texto_guardado, estado
    except Exception as exc:
        return '', f'No fue posible analizar esta imagen automáticamente: {exc}. Puede ingresar datos manualmente.'
