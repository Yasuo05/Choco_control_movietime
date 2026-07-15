"""Asociación automática de fotografías del catálogo mediante el código del producto.

Las fotografías se guardan en ``media/imagenes_productos``. Cada presentación
física utiliza su propio código: ``2611.jpg`` para el combo con vaso y
``2768.jpg`` para la presentación con botella. Esta separación también se usa
en los reportes para mostrar la imagen del código que finalmente se digita en
Up Base.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from django.conf import settings

from .models import Producto

EXTENSIONES_PERMITIDAS = {'.jpg', '.jpeg', '.png', '.webp'}
CARPETA_CATALOGO = 'imagenes_productos'


def normalizar_codigo_archivo(codigo: str | None) -> str:
    """Iguala códigos numéricos con ceros iniciales: 003088 y 3088."""
    valor = (codigo or '').strip()
    if valor.isdigit():
        return str(int(valor)) if int(valor) else '0'
    return valor.casefold()


def carpeta_imagenes_productos() -> Path:
    carpeta = Path(settings.MEDIA_ROOT) / CARPETA_CATALOGO
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def indexar_imagenes() -> tuple[dict[str, str], dict[str, str]]:
    """Devuelve índices por nombre exacto y por código normalizado."""
    exactas: dict[str, str] = {}
    normalizadas: dict[str, str] = {}
    for archivo in sorted(carpeta_imagenes_productos().iterdir()):
        if not archivo.is_file() or archivo.suffix.lower() not in EXTENSIONES_PERMITIDAS:
            continue
        codigo = archivo.stem.strip()
        if not codigo:
            continue
        exactas.setdefault(codigo, archivo.name)
        normalizadas.setdefault(normalizar_codigo_archivo(codigo), archivo.name)
    return exactas, normalizadas


def _informacion_imagen(codigo: str, exactas: dict[str, str], normalizadas: dict[str, str]) -> dict[str, str]:
    codigo = (codigo or '').strip()
    archivo = ''
    if codigo in exactas:
        archivo = exactas[codigo]
    elif codigo and normalizar_codigo_archivo(codigo) in normalizadas:
        archivo = normalizadas[normalizar_codigo_archivo(codigo)]
    base_url = f"{settings.MEDIA_URL.rstrip('/')}/{CARPETA_CATALOGO}/"
    return {
        'imagen_catalogo_archivo': archivo,
        'imagen_catalogo_url': base_url + quote(archivo) if archivo else '',
        'codigo_sugerido_imagen': codigo,
    }


def _codigo_fotografia_producto(producto: Producto) -> str:
    """Código exclusivo para la tarjeta general existente en la base."""
    return (producto.codigo_vaso or producto.codigo_botella or '').strip()


def _depurar_duplicados_de_vista_general(productos: list[Producto]) -> list[Producto]:
    """Oculta la fila botella redundante cuando la relación ya vive en una sola tarjeta vaso → botella.

    Los combos dulces/mixtos se cargaron inicialmente en dos filas: la relación convertible
    y otra fila independiente para la presentación botella. En la vista técnica general esto
    producía dos tarjetas para el mismo combo. Cuando un código botella tiene exactamente un
    origen convertible, basta mostrar la relación completa en su tarjeta convertible.

    No se oculta la botella compartida por varios vasos, como la gaseosa 2097, porque es una
    presentación individual independiente y tiene varios posibles orígenes.
    """
    origenes_por_botella: dict[str, list[Producto]] = {}
    for producto in productos:
        if producto.convertible and producto.codigo_vaso and producto.codigo_botella:
            clave = normalizar_codigo_archivo(producto.codigo_botella)
            origenes_por_botella.setdefault(clave, []).append(producto)

    codigos_representados = {
        clave for clave, origenes in origenes_por_botella.items() if len(origenes) == 1
    }
    return [
        producto for producto in productos
        if not (
            not producto.convertible
            and not producto.codigo_vaso
            and producto.codigo_botella
            and normalizar_codigo_archivo(producto.codigo_botella) in codigos_representados
        )
    ]


def adjuntar_imagenes_catalogo(productos) -> tuple[list[Producto], int]:
    """Añade fotografía propia a tarjetas de la vista general, sin duplicar presentaciones botella."""
    exactas, normalizadas = indexar_imagenes()
    resultado = _depurar_duplicados_de_vista_general(list(productos))
    encontrados = 0
    for producto in resultado:
        info = _informacion_imagen(_codigo_fotografia_producto(producto), exactas, normalizadas)
        for clave, valor in info.items():
            setattr(producto, clave, valor)
        if info['imagen_catalogo_url']:
            encontrados += 1
    return resultado, encontrados


@dataclass
class TarjetaPresentacion:
    """Tarjeta visual de un producto tal como se entrega al cliente."""

    producto: Producto
    presentacion: str
    nombre: str
    categoria: str
    descripcion: str
    codigo: str
    relacion_etiqueta: str = ''
    relacion_codigo: str = ''
    imagen_catalogo_url: str = ''
    imagen_catalogo_archivo: str = ''
    codigo_sugerido_imagen: str = ''

    @property
    def confirmado(self) -> bool:
        return self.producto.confirmado

    @property
    def convertible(self) -> bool:
        return self.producto.convertible

    @property
    def pk(self) -> int:
        return self.producto.pk


def _tarjeta_vaso(producto: Producto) -> TarjetaPresentacion:
    return TarjetaPresentacion(
        producto=producto,
        presentacion='VASO' if producto.convertible else 'DIRECTA',
        nombre=producto.nombre,
        categoria=producto.categoria,
        descripcion=producto.descripcion_vaso or producto.nombre,
        codigo=producto.codigo_vaso,
        relacion_etiqueta='Código botella' if producto.convertible and producto.codigo_botella else '',
        relacion_codigo=producto.codigo_botella if producto.convertible else '',
    )


def _tarjetas_botella(productos: list[Producto]) -> list[TarjetaPresentacion]:
    """Crea una tarjeta por código botella, sin duplicar productos equivalentes."""
    por_codigo: dict[str, list[Producto]] = {}
    orden: list[str] = []
    for producto in productos:
        if not producto.codigo_botella:
            continue
        clave = normalizar_codigo_archivo(producto.codigo_botella)
        if clave not in por_codigo:
            por_codigo[clave] = []
            orden.append(clave)
        por_codigo[clave].append(producto)

    tarjetas: list[TarjetaPresentacion] = []
    for clave in orden:
        candidatos = por_codigo[clave]
        directos = [p for p in candidatos if not p.convertible and not p.codigo_vaso]
        convertibles = [p for p in candidatos if p.convertible and p.codigo_vaso]
        base = directos[0] if directos else convertibles[0]
        codigo = base.codigo_botella
        codigos_origen = ' · '.join(p.codigo_vaso for p in convertibles if p.codigo_vaso)
        if directos:
            nombre = base.nombre
            descripcion = base.descripcion_botella or base.nombre
        else:
            nombre = f'{base.nombre} · botella'
            descripcion = base.descripcion_botella or nombre
        tarjetas.append(TarjetaPresentacion(
            producto=base,
            presentacion='BOTELLA',
            nombre=nombre,
            categoria=base.categoria,
            descripcion=descripcion,
            codigo=codigo,
            relacion_etiqueta='Proviene de vaso' if codigos_origen else '',
            relacion_codigo=codigos_origen,
        ))
    return tarjetas


def construir_tarjetas_presentacion(productos, vista: str) -> tuple[list[TarjetaPresentacion], int]:
    """Construye las tarjetas físicas para la presentación vaso o botella."""
    exactas, normalizadas = indexar_imagenes()
    lista = list(productos)
    if vista == 'botella':
        tarjetas = _tarjetas_botella(lista)
    else:
        tarjetas = [_tarjeta_vaso(producto) for producto in lista if producto.codigo_vaso]

    encontrados = 0
    for tarjeta in tarjetas:
        info = _informacion_imagen(tarjeta.codigo, exactas, normalizadas)
        tarjeta.imagen_catalogo_url = info['imagen_catalogo_url']
        tarjeta.imagen_catalogo_archivo = info['imagen_catalogo_archivo']
        tarjeta.codigo_sugerido_imagen = info['codigo_sugerido_imagen']
        if tarjeta.imagen_catalogo_url:
            encontrados += 1
    return tarjetas, encontrados


def adjuntar_imagenes_reporte(filas: list[dict]) -> tuple[list[dict], int]:
    """Asocia al reporte la foto del código final que se digitara en Up Base."""
    exactas, normalizadas = indexar_imagenes()
    encontrados = 0
    for fila in filas:
        info = _informacion_imagen(str(fila.get('codigo_final', '')), exactas, normalizadas)
        fila.update(info)
        if info['imagen_catalogo_url']:
            encontrados += 1
    return filas, encontrados


def adjuntar_imagenes_movimientos(movimientos) -> tuple[list, int]:
    """Muestra en cada movimiento la foto de la presentación final resultante."""
    exactas, normalizadas = indexar_imagenes()
    lista = list(movimientos)
    encontrados = 0
    for movimiento in lista:
        info = _informacion_imagen(movimiento.codigo_final, exactas, normalizadas)
        for clave, valor in info.items():
            setattr(movimiento, clave, valor)
        if info['imagen_catalogo_url']:
            encontrados += 1
    return lista, encontrados
