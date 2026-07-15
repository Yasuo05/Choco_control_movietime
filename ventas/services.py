from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
import re
from pathlib import Path
from typing import Iterable

from .models import Cierre, Jornada, Producto
from .ocr_reader import ejecutar_ocr_embebido, leer_filas_serializadas


@dataclass
class Movimiento:
    cierre_numero: int
    modalidad: str
    codigo_leido: str
    codigo_final: str
    cantidad: int
    producto: Producto | None
    convertido: bool = False
    advertencia: str = ''
    caja_nombre: str = ''
    cantidad_anterior: int = 0
    cantidad_acumulada: int = 0

    @property
    def nombre_producto(self) -> str:
        if not self.producto:
            return 'Código no registrado en catálogo'
        usa_presentacion_botella = bool(
            self.producto.codigo_botella
            and codigos_equivalentes(self.codigo_final, self.producto.codigo_botella)
            and (
                not self.producto.codigo_vaso
                or not codigos_equivalentes(self.codigo_final, self.producto.codigo_vaso)
            )
        )
        if usa_presentacion_botella and self.producto.descripcion_botella:
            return self.producto.descripcion_botella
        return self.producto.nombre

    @property
    def presentacion_final(self) -> str:
        """Presentación física representada por el código final del reporte."""
        if self.convertido:
            return 'Botella'
        if self.producto and self.producto.codigo_botella and codigos_equivalentes(self.codigo_final, self.producto.codigo_botella):
            if not self.producto.codigo_vaso or not codigos_equivalentes(self.codigo_final, self.producto.codigo_vaso):
                return 'Botella'
        if self.producto and self.producto.convertible and self.producto.codigo_vaso and codigos_equivalentes(self.codigo_final, self.producto.codigo_vaso):
            return 'Vaso'
        return 'Venta directa'


def normalizar_codigo(codigo: str) -> str:
    return re.sub(r'\s+', '', str(codigo or '').strip()).upper()


def clave_codigo(codigo: str) -> str:
    codigo = normalizar_codigo(codigo)
    if codigo.isdigit():
        return codigo.lstrip('0') or '0'
    return codigo


def codigos_equivalentes(codigo_a: str, codigo_b: str) -> bool:
    return clave_codigo(codigo_a) == clave_codigo(codigo_b)


def buscar_producto_por_codigo(codigo: str, productos: Iterable[Producto]) -> Producto | None:
    productos = list(productos)
    # Primero se reconoce el código de venta normal; luego una botella vendida directamente.
    # Así 2097 se describe como "Gaseosa botella" y no como uno de los vasos convertibles.
    for producto in productos:
        if producto.codigo_vaso and codigos_equivalentes(codigo, producto.codigo_vaso):
            return producto
    for producto in productos:
        if not producto.convertible and producto.codigo_botella and codigos_equivalentes(codigo, producto.codigo_botella):
            return producto
    for producto in productos:
        if producto.codigo_botella and codigos_equivalentes(codigo, producto.codigo_botella):
            return producto
    return None


def es_codigo_vaso(codigo: str, producto: Producto | None) -> bool:
    return bool(producto and producto.codigo_vaso and codigos_equivalentes(codigo, producto.codigo_vaso))


def codigo_canonico(codigo: str, producto: Producto | None, convertido: bool = False) -> str:
    """Entrega un único código de salida; evita separar 2097 de 002097."""
    codigo = normalizar_codigo(codigo)
    if producto:
        if convertido and producto.codigo_botella:
            return normalizar_codigo(producto.codigo_botella)
        if producto.codigo_vaso and codigos_equivalentes(codigo, producto.codigo_vaso):
            return normalizar_codigo(producto.codigo_vaso)
        if producto.codigo_botella and codigos_equivalentes(codigo, producto.codigo_botella):
            return normalizar_codigo(producto.codigo_botella)
    return codigo


def movimientos_de_jornada(jornada: Jornada) -> tuple[list[Movimiento], list[str]]:
    """Calcula ventas nuevas por periodo utilizando solo cierres ya revisados."""
    productos = list(Producto.objects.filter(activo=True).order_by('-confirmado', 'id'))
    cantidades_previas: dict[str, int] = {}
    movimientos: list[Movimiento] = []
    advertencias: list[str] = []

    pendiente_previo = False
    for cierre in jornada.cierres.prefetch_related('detalles', 'productos_convertir').all().order_by('numero'):
        if pendiente_previo:
            advertencias.append(
                f'Cierre {cierre.numero} de {jornada.caja.nombre}: no se calcula hasta validar el cierre anterior pendiente.'
            )
            continue
        if not cierre.confirmado:
            if cierre.detalles.exists() or cierre.imagen:
                advertencias.append(
                    f'Cierre {cierre.numero} de {jornada.caja.nombre}: está pendiente de revisión y no se incluye en el reporte.'
                )
            pendiente_previo = True
            continue
        seleccionados = list(cierre.productos_convertir.all())
        for detalle in cierre.detalles.all():
            codigo = normalizar_codigo(detalle.codigo_leido)
            clave = clave_codigo(codigo)
            anterior = cantidades_previas.get(clave, 0)
            delta = detalle.cantidad_acumulada - anterior
            cantidades_previas[clave] = detalle.cantidad_acumulada

            if delta < 0:
                mensaje = (
                    f'Cierre {cierre.numero}: el código {codigo} disminuye de {anterior} a '
                    f'{detalle.cantidad_acumulada}. Revise los datos acumulados.'
                )
                advertencias.append(mensaje)
                movimientos.append(
                    Movimiento(
                        cierre_numero=cierre.numero, modalidad=cierre.modalidad_periodo, codigo_leido=codigo,
                        codigo_final=codigo, cantidad=delta, producto=None, convertido=False,
                        advertencia=mensaje, caja_nombre=jornada.caja.nombre,
                        cantidad_anterior=anterior, cantidad_acumulada=detalle.cantidad_acumulada,
                    )
                )
                continue
            if delta == 0:
                continue

            producto = buscar_producto_por_codigo(codigo, productos)
            codigo_final = codigo_canonico(codigo, producto)
            convertido = False

            cumple_conversion = bool(
                cierre.modalidad_periodo == Cierre.Modalidad.BOTELLA
                and producto
                and producto.convertible
                and producto.codigo_botella
                and es_codigo_vaso(codigo, producto)
            )
            restringido_por_seleccion = bool(seleccionados)
            producto_seleccionado = producto in seleccionados if producto else False

            if cumple_conversion and not producto.confirmado:
                advertencias.append(
                    f'Cierre {cierre.numero}: {producto.nombre} no se convirtió porque su equivalencia no está confirmada.'
                )
            elif cumple_conversion and (not restringido_por_seleccion or producto_seleccionado):
                codigo_final = codigo_canonico(producto.codigo_botella, producto, convertido=True)
                convertido = True

            if producto is None:
                advertencias.append(
                    f'Cierre {cierre.numero}: el código {codigo} no existe en el catálogo; se mantiene sin transformación.'
                )

            movimientos.append(
                Movimiento(
                    cierre_numero=cierre.numero,
                    modalidad=cierre.modalidad_periodo,
                    codigo_leido=codigo,
                    codigo_final=codigo_final,
                    cantidad=delta,
                    producto=producto,
                    convertido=convertido,
                    caja_nombre=jornada.caja.nombre,
                    cantidad_anterior=anterior,
                    cantidad_acumulada=detalle.cantidad_acumulada,
                )
            )

    return movimientos, advertencias


def agrupar_movimientos(movimientos: Iterable[Movimiento]) -> list[dict]:
    agrupado: dict[str, dict] = {}
    for mov in movimientos:
        if mov.cantidad <= 0:
            continue
        clave = clave_codigo(mov.codigo_final)
        if clave not in agrupado:
            agrupado[clave] = {
                'codigo_final': mov.codigo_final,
                'cantidad': 0,
                'producto': mov.nombre_producto,
                'cajas': set(),
                'presentaciones': set(),
            }
        agrupado[clave]['cantidad'] += mov.cantidad
        agrupado[clave]['presentaciones'].add(mov.presentacion_final)
        if mov.caja_nombre:
            agrupado[clave]['cajas'].add(mov.caja_nombre)
        if agrupado[clave]['producto'] == 'Código no registrado en catálogo' and mov.producto:
            agrupado[clave]['producto'] = mov.nombre_producto
        # Ante variantes como 002097/2097 se conserva el código canónico del catálogo.
        if mov.producto:
            agrupado[clave]['codigo_final'] = mov.codigo_final
    filas = []
    for fila in agrupado.values():
        fila['cajas'] = ', '.join(sorted(fila['cajas']))
        fila['presentacion'] = ' / '.join(sorted(fila.pop('presentaciones')))
        filas.append(fila)
    return sorted(filas, key=lambda fila: clave_codigo(fila['codigo_final']))


def consolidado_de_jornada(jornada: Jornada) -> list[dict]:
    movimientos, _ = movimientos_de_jornada(jornada)
    return agrupar_movimientos(movimientos)


def consolidado_por_fecha(fecha: date) -> tuple[list[dict], list[str]]:
    movimientos: list[Movimiento] = []
    advertencias: list[str] = []
    jornadas = Jornada.objects.filter(fecha=fecha).select_related('caja').order_by('caja__nombre')
    for jornada in jornadas:
        movs, alerts = movimientos_de_jornada(jornada)
        movimientos.extend(movs)
        advertencias.extend(alerts)
    return agrupar_movimientos(movimientos), advertencias


def ejecutar_ocr(ruta_imagen: str | Path) -> tuple[str, str]:
    """Analiza la boleta con los modelos OCR incluidos en el proyecto."""
    codigos = []
    for producto in Producto.objects.filter(activo=True).only('codigo_vaso', 'codigo_botella'):
        if producto.codigo_vaso:
            codigos.append(producto.codigo_vaso)
        if producto.codigo_botella:
            codigos.append(producto.codigo_botella)
    return ejecutar_ocr_embebido(ruta_imagen, codigos)


def filas_detectadas_desde_ocr(texto: str) -> list[dict]:
    return [
        {
            'codigo': fila.codigo,
            'cantidad': fila.cantidad,
            'descripcion': fila.descripcion,
            'alerta': fila.alerta,
        }
        for fila in leer_filas_serializadas(texto)
    ]


def sugerir_detalles_desde_ocr(texto: str) -> str:
    """Entrega código,cantidad listos para edición a partir de la tabla OCR detectada."""
    filas_estructuradas = leer_filas_serializadas(texto)
    if filas_estructuradas:
        return '\n'.join(
            f'{fila.codigo},{fila.cantidad if fila.cantidad is not None else "REVISAR"}'
            for fila in filas_estructuradas
        )

    # Compatibilidad con lecturas guardadas por versiones anteriores.
    sugerencias: list[str] = []
    vistos: set[str] = set()
    patrones = [
        re.compile(r'^\s*(\d{1,7})\b.*?\b(\d+)\s*$'),
        re.compile(r'^\s*(\d{1,7})\s*[,;|:\-]\s*(\d+)\s*$'),
    ]
    for linea in texto.splitlines():
        for patron in patrones:
            coincidencia = patron.match(linea)
            if coincidencia:
                codigo, cantidad = coincidencia.groups()
                linea_sugerida = f'{clave_codigo(codigo)},{cantidad}'
                if linea_sugerida not in vistos:
                    vistos.add(linea_sugerida)
                    sugerencias.append(linea_sugerida)
                break
    return '\n'.join(sugerencias)


def parsear_detalles_texto(texto: str, permitir_vacio: bool = False) -> tuple[list[tuple[str, int]], list[str]]:
    filas: list[tuple[str, int]] = []
    errores: list[str] = []
    vistos: set[str] = set()
    for numero_linea, linea in enumerate(texto.splitlines(), start=1):
        linea = linea.strip()
        if not linea:
            continue
        partes = [parte.strip() for parte in re.split(r'[,;|\t]', linea) if parte.strip()]
        if len(partes) != 2:
            errores.append(f'Línea {numero_linea}: use el formato CODIGO,CANTIDAD.')
            continue
        codigo = normalizar_codigo(partes[0])
        if not codigo:
            errores.append(f'Línea {numero_linea}: el código está vacío.')
            continue
        try:
            cantidad = int(partes[1])
        except ValueError:
            errores.append(f'Línea {numero_linea}: la cantidad debe ser un número entero.')
            continue
        if cantidad < 0:
            errores.append(f'Línea {numero_linea}: la cantidad no puede ser negativa.')
            continue
        clave = clave_codigo(codigo)
        if clave in vistos:
            errores.append(f'Línea {numero_linea}: el código {codigo} está repetido o equivale a otro código ya ingresado.')
            continue
        vistos.add(clave)
        filas.append((codigo, cantidad))
    if not filas and not errores and not permitir_vacio:
        errores.append('Ingrese al menos una línea con CODIGO,CANTIDAD.')
    return filas, errores
