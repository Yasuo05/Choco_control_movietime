# Catálogo actualizado para operación

## Retirados según revisión del usuario

- Combo Futbolero: pop grande + botella (`3539`).
- Combo Futbolero: pop grande + botella + hot dog (`3541`).
- Gaseosa botella alternativa (`2750`).
- Sonic lata + 2 botellas (`3559`).
- Sonic lata + 2 botellas + hot dog (`3561`).
- Variante anterior de gaseosa botella (`002097`), reemplazada por `2097`.

## Confirmados o agregados en esta revisión

- Chicha botella (`3090`).
- Gaseosa botella (`2097`).
- Gaseosa vaso chico (`2085`), mediano (`2086`) y grande (`2087`), convertibles a botella `2097` durante un periodo botella.
- Gomita Ambrosito (`1911`), Hot dog individual (`1677`).
- Pop corn salado: chico (`31`), mediano (`32`), grande (`33`), gigante (`47`).
- Pop corn dulce: chico (`2606`), mediano (`2607`), grande (`2608`), gigante (`2609`).
- Dulces: Wafer (`9`), Travesuras (`4`), Sublime (`13`), Lenteja cajita 30 gr (`16`), Cañonazo (`2527`).
- Agua San Luis (`26`).
- Combo 1 dulce: `2611` vaso → `2768` botella.
- Combo 2 dulce: `2612` vaso → `2769` botella.
- Combo 3 mix: `2613` vaso → `002770` botella.
- Combo 4 mix: `2614` vaso → `002771` botella.

El catálogo permanece editable desde la pantalla **Productos**.


## Productos identificados en la boleta de referencia

Además se incorporaron como ventas directas editables: Promo Yape (`3425`), Combo Yape (`2872`), Super pizza personal (`2860`) y Papa Inka Chips (`3331`). Los códigos `2611`, `2612`, `2613` y `2614` ahora están vinculados a sus equivalentes en botella y se convierten cuando corresponde.

## OCR interno

El lector analiza la columna **Cant.** y excluye **P.Total**. Los códigos con ceros impresos se normalizan para operación (`003088 → 3088`, `001911 → 1911`, `004 → 4`). Las filas marcadas o no reconocidas se dejan visibles para corrección antes del reporte.

## Identificados en boleta limpia adicional

Se agregaron como ventas directas: Combo BBVA/Plin (`3845`), Combo Mantequilla Pop (`3971`), Gelatines (`3653`), Nachos 90 gramos (`2899`), Combo Galáctico (`4171`), Refil Galáctico gigante (`4177`) y Combo Legado (`4181`). Su equivalencia a botella no se presume y permanece sin conversión automática.

El OCR ahora recorta automáticamente boletas limpias fotografiadas sobre fondo visible, descarta secciones anteriores a **Detalle de productos** y corrige el desplazamiento de la columna Cant. causado por la perspectiva.
