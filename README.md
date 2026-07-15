# Choco Control · Up Base

## Actualización v14 · carrusel durante el análisis de boletas

- Al presionar **Analizar imágenes cargadas**, la aplicación muestra una ventana de procesamiento con las fotos seleccionadas en carrusel.
- El carrusel identifica el método de venta y el nombre del archivo para cada boleta cargada.
- Mientras el OCR se ejecuta, se muestran etapas visuales: preparación, localización de productos, lectura de códigos y cantidades, verificación y **Casi listo**.
- El indicador de avance es informativo: la revisión aparece automáticamente cuando el servidor concluye el análisis real.
- Antes de enviar, cada casilla muestra una miniatura de la boleta seleccionada.

## Actualización v13 · eliminar registros del día

- Desde **Inicio** y desde el **Reporte final diario** se puede eliminar una fecha completa previa confirmación.
- Se eliminan las jornadas, cierres, detalles y fotografías de boleta de esa fecha; se conservan el catálogo y las imágenes de productos.

## Actualización v12 · catálogo sin duplicados, eliminación segura e inicio por fecha

- La **Vista general** ya no repite una tarjeta independiente para los combos dulces/mixtos cuya presentación botella ya está incluida en su relación vaso → botella. Se integran: `2611 → 2768`, `2612 → 2769`, `2613 → 002770` y `2614 → 002771`.
- Se mantiene **Gaseosa botella `2097`** como producto independiente porque también puede venderse sola y es el resultado común de los vasos `2085`, `2086` y `2087`.
- En **Productos** aparece la acción **Eliminar**. La eliminación solicita confirmación y se bloquea cuando el producto interviene en cierres registrados que podrían cambiar un reporte histórico.
- La pantalla de **Inicio** se agrupa por fecha: muestra el día de hoy y, al abrir una fecha, recién se consultan los métodos/cajas registrados y su consolidado.
- Para limpiar una base copiada desde una versión anterior sin borrar cierres ni imágenes, ejecute `CORREGIR_DUPLICADOS_CATALOGO.bat`.

# Choco Control · Reporte diario para Up Base

Aplicación web local en **Python + Django** para cargar boletas acumuladas de hasta cuatro métodos de venta, analizar cada fotografía con OCR interno y generar un único reporte diario de **código + cantidad** para digitar en Up Base.


## Actualización v9 · vista por presentación e imágenes en el reporte

La pantalla **Productos** ahora cuenta con tres vistas:

- **Presentación vaso**: muestra la foto y el código del producto cuando se entrega con vaso.
- **Presentación botella**: muestra la foto y el código final cuando el producto se entrega con botella.
- **Vista general**: conserva la edición técnica de relaciones vaso → botella.

Cada presentación utiliza una foto diferente, nombrada con el código que se digita en Up Base. Por ejemplo:

| Presentación | Archivo de foto | Código mostrado |
|---|---:|---:|
| Combo 1 dulce con vaso | `2611.jpg` | 2611 |
| Combo 1 dulce con botella | `2768.jpg` | 2768 |
| Gaseosa botella | `2097.jpg` | 2097 |

El **Reporte final diario** y el **detalle de la jornada** ahora muestran una miniatura del producto final. Si un combo se vendió con vaso y también con botella el mismo día, se mantienen dos líneas diferentes en el reporte, cada una con su código, cantidad e imagen correspondiente.

## Actualización v8 · combos dulces y mixtos vinculados a botella

Los combos dulces/mixtos encontrados en las boletas ahora se convierten a su código de botella cuando el periodo está marcado como **Botella**:

| Producto | Vaso | Botella |
|---|---:|---:|
| Combo 1 dulce | 2611 | 2768 |
| Combo 2 dulce | 2612 | 2769 |
| Combo 3 mix | 2613 | 002770 |
| Combo 4 mix | 2614 | 002771 |

La corrección de fotografías de v6 se conserva: la imagen de un código botella no se reutiliza en los productos vaso que pueden convertirse a ella. Por ejemplo, `2097.webp` aparece solamente en **Gaseosa botella**; para mostrar fotos de **Gaseosa vaso chico**, **mediano** y **grande** se deben usar `2085.webp`, `2086.webp` y `2087.webp`, respectivamente.

## Cambio principal de esta versión

La pantalla principal ahora permite cargar, en un solo registro diario, hasta cuatro fotografías independientes:

1. Presencial
2. Kio 1
3. Kio 2
4. Ventas online

Cada fotografía es opcional. Si solo existe la boleta de una o dos cajas, las demás casillas se dejan vacías y el proceso continúa sin error.

## Flujo de trabajo

1. Abra **Cargar fotos del día**.
2. Indique la fecha y adjunte las boletas disponibles en sus casillas respectivas.
3. Para cada imagen subida, seleccione si las ventas nuevas del periodo se entregaron en vaso o en botella.
4. El sistema detecta las filas de la boleta tomando el código de la columna **Descripción** y la cantidad de la columna **Cant.**; **P.Total** se ignora. Revise los resultados antes de confirmar. Una imagen puede quedar pendiente sin bloquear las demás cajas.
5. Abra el **Reporte final diario para Up Base** y exporte el consolidado a Excel o CSV.

También permanece disponible el registro manual avanzado por caja y por cierre.

## Reglas de cálculo implementadas

- Cada método de venta mantiene sus propios cierres acumulados por fecha.
- El segundo cierre de una caja calcula solo la diferencia contra el cierre anterior de esa misma caja.
- Cuando un periodo se marca como botella, únicamente las equivalencias confirmadas convierten su código vaso al código botella.
- Un cierre pendiente impide calcular cierres posteriores de **esa misma caja**, pero no bloquea las demás cajas.
- Códigos equivalentes con ceros iniciales se consolidan en una sola fila. Para la gaseosa botella se utiliza el código operativo solicitado: **2097**.

## Catálogo operativo cargado

### Combos convertibles vaso → botella

| Producto | Vaso | Botella |
|---|---:|---:|
| Combo 1 con hot dog | 3088 | 3089 |
| Combo 1 sin hot dog | 2512 | 002498 |
| Combo 2 con hot dog | 2518 | 002520 |
| Combo 2 sin hot dog | 2517 | 002519 |
| Combo 3 con hot dog | 2485 | 002503 |
| Combo 3 sin hot dog | 2484 | 002502 |
| Combo 4 con hot dog | 2489 | 002505 |
| Combo 4 sin hot dog | 2488 | 002504 |
| Combo Power | 3135 | 002834 |
| Combo 1 dulce | 2611 | 2768 |
| Combo 2 dulce | 2612 | 2769 |
| Combo 3 mix | 2613 | 002770 |
| Combo 4 mix | 2614 | 002771 |

### Bebidas individuales convertibles

| Producto | Vaso | Botella |
|---|---:|---:|
| Gaseosa vaso chico | 2085 | 2097 |
| Gaseosa vaso mediano | 2086 | 2097 |
| Gaseosa vaso grande | 2087 | 2097 |

### Botellas directas y combos ya embotellados

| Producto | Código |
|---|---:|
| Combo 1 dulce con botella | 2768 |
| Combo 2 dulce con 2 botellas | 2769 |
| Combo 3 mix con 2 botellas | 002770 |
| Combo 4 mix con 3 botellas | 002771 |
| Chicha botella | 3090 |
| Gaseosa botella | 2097 |

### Ventas individuales

| Producto | Código |
|---|---:|
| Gomita Ambrosito | 1911 |
| Hot dog individual | 1677 |
| Pop corn chico salado | 31 |
| Pop corn mediano salado | 32 |
| Pop corn grande salado | 33 |
| Pop corn gigante salado | 47 |
| Pop corn chico dulce | 2606 |
| Pop corn mediano dulce | 2607 |
| Pop corn grande dulce | 2608 |
| Pop corn gigante dulce | 2609 |
| Wafer | 9 |
| Travesuras | 4 |
| Sublime | 13 |
| Lenteja cajita 30 gr | 16 |
| Cañonazo | 2527 |
| Agua San Luis | 26 |
| Promo Yape: 2 pop salado chico | 3425 |
| Combo Yape: 1 pop salado gigante + 2 | 2872 |
| Super pizza personal | 2860 |
| Papa Inka Chips | 3331 |

Se retiraron del catálogo operativo las filas: Combo Futbolero `3539`, Combo Futbolero con hot dog `3541`, gaseosa alternativa `2750` y los productos Sonic `3559` y `3561`. La antigua variante `002097` fue reemplazada por `2097` para Gaseosa botella.

## Forma sencilla de abrirlo en Windows

1. Descomprima el ZIP.
2. Abra la carpeta `choco_upbase_web`.
3. La primera vez, haga doble clic en `INSTALAR_Y_ABRIR_WINDOWS.bat`. Este paso instala las librerías Python requeridas y abre la aplicación. Los modelos OCR ya vienen incluidos en el ZIP.
4. Las siguientes veces, utilice `ABRIR_CHOCO_CONTROL.bat`.

No necesita instalar Tesseract.

### Actualizar una instalación anterior sin perder cierres

Si ya tiene datos cargados en una versión anterior, copie su archivo `db.sqlite3` y su carpeta `media/` a esta versión, y luego ejecute `ACTUALIZAR_COMBOS_DULCES.bat`. El proceso actualiza únicamente el catálogo y conserva jornadas, cierres y fotografías.

## Instalación en Windows

```powershell
cd choco_upbase_web
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py cargar_catalogo_inicial
python manage.py runserver
```

Abra el navegador en `http://127.0.0.1:8000/`.

El ZIP ya contiene el catálogo actualizado y los cuatro métodos de venta. La base se entrega sin jornadas ni cierres cargados, lista para subir sus boletas. Para probar únicamente el cálculo acumulado con un ejemplo artificial puede ejecutar:

```powershell
python manage.py cargar_demostracion
python manage.py runserver
```

Para borrar posteriormente las jornadas y conservar el catálogo:

```powershell
python manage.py limpiar_jornadas
```

## Lectura de boletas por OCR interno

Esta versión **no utiliza Tesseract** ni requiere instalar un ejecutable externo. El ZIP incluye en la carpeta `ocr_models` los modelos locales usados por el lector; `pip install -r requirements.txt` instala solamente las librerías Python necesarias para ejecutarlos.

El lector fue adaptado a boletas fotografiadas completas, limpias o resaltadas. Cuando el papel aparece sobre un fondo visible, recorta automáticamente la zona central de la boleta antes del análisis y utiliza únicamente la sección **Detalle de productos**, aunque existan tablas anteriores como **Ventas por forma de pago**.

El lector fue adaptado al formato de boleta recibido:

- identifica productos en la columna **Descripción**;
- extrae la cifra de la columna **Cant.**;
- ignora el monto de **P.Total**;
- normaliza códigos impresos con ceros a la izquierda, por ejemplo `003088 → 3088` y `001911 → 1911`;
- realiza una segunda lectura de celdas resaltadas para reducir errores del marcador amarillo;
- muestra `REVISAR` cuando una cantidad no pudo leerse con seguridad, evitando que el producto desaparezca del registro;
- ajusta la relación entre las columnas por perspectiva para evitar correr las cantidades a la fila siguiente en fotos inclinadas;
- conserva códigos nuevos como `4171`, `4177` y `4181` sin confundirlos con el código `4`.

La lectura OCR siempre requiere revisión humana antes de formar parte del consolidado.

## Verificación incluida

El proyecto contiene pruebas automáticas para:

- Conversión únicamente de la diferencia del periodo botella.
- Rechazo de conversión cuando la equivalencia no está confirmada.
- Consolidación de `2097` y `002097` como una sola gaseosa.
- Consolidado diario que suma distintas cajas.
- Carga de una sola foto mientras las otras tres casillas quedan vacías.
- Extracción estructurada de filas con el formato Descripción / Cant. / P.Total.
- Conversión de combos dulces/mixtos `2611`, `2612`, `2613` y `2614` a sus equivalentes de botella.
- Separación visual de tarjetas e imágenes entre presentación vaso y botella.
- Visualización de la foto del código final en el reporte, manteniendo filas distintas cuando hubo ventas con vaso y botella.

Para ejecutarlas:

```powershell
python manage.py test
```


### Productos adicionales observados en boleta limpia

Se incorporaron como ventas directas editables, sin conversión automática por no contar aún con equivalencia confirmada: `3845` Combo BBVA/Plin, `3971` Combo Mantequilla Pop, `3653` Gelatines, `2899` Nachos 90 gramos, `4171` Combo Galáctico, `4177` Refil Galáctico gigante y `4181` Combo Legado.


## Catálogo visual con fotos por código

La pantalla `http://127.0.0.1:8000/productos/` muestra los productos en tarjetas visuales separadas por presentación. Para asignar fotografías no es necesario editar la base de datos ni subirlas desde un formulario:

1. Haga doble clic en `ABRIR_CARPETA_IMAGENES.bat` o abra manualmente la carpeta `media/imagenes_productos/`.
2. Copie allí la foto de cada presentación.
3. Cambie el nombre del archivo por el código correspondiente, por ejemplo `2611.jpg` para el combo dulce con vaso y `2768.jpg` para el mismo combo con botella.
4. Recargue la página de Productos y elija **Presentación vaso** o **Presentación botella**.

Formatos permitidos: `.jpg`, `.jpeg`, `.png` y `.webp`. Los códigos con ceros iniciales se reconocen como el mismo producto (`003088` y `3088`). Cada presentación usa únicamente su código final: una foto `2097.webp` se muestra en **Gaseosa botella**, mientras que `2085.webp`, `2086.webp` y `2087.webp` corresponden exclusivamente a los tres vasos. Las mismas imágenes se muestran como referencia en los reportes y no alteran los cálculos para Up Base.

## Actualización v10: reporte diario a ancho completo

En el reporte final diario, la tarjeta **Digitar en Up Base** se muestra debajo de **Vías incluidas** y utiliza el ancho completo de la pantalla. La tabla separa producto/presentación, código Up Base, vías incluidas y cantidad; la lógica de cálculo y las exportaciones se mantienen sin cambios.

## Mejora visual v11: reporte diario más legible

El reporte final diario mantiene el consolidado debajo de **Vías incluidas** y ahora utiliza miniaturas más grandes, mayor tamaño de texto y códigos/cantidades destacados para facilitar la digitación en Up Base. Esta mejora es únicamente visual; no modifica los cierres ni las reglas de conversión.


## Eliminar registros de una fecha

Desde **Inicio**, en la tabla **Cierres por fecha**, utilice **Eliminar registros** para limpiar un día completo. La opción también aparece dentro del reporte final del día.

Antes de borrar, el sistema presenta una confirmación con el número de métodos, cierres y filas de productos afectados. Al confirmar se eliminan:

- Cierres registrados para la fecha seleccionada.
- Cantidades revisadas asociadas a esos cierres.
- Fotografías de boletas cargadas para esos cierres.

Se conservan el catálogo de productos, las equivalencias vaso/botella, las imágenes del catálogo y todos los registros correspondientes a otras fechas.


## Regla operativa v16: boletas acumuladas por vía de venta

Las vías operativas son **Presencial**, **Kio 1**, **Kio 2** y **Ventas online**. Cada vía mantiene su propio acumulado diario. Si se suben dos boletas de Presencial para la misma fecha, la segunda no se suma completa: la aplicación resta el acumulado anterior por código y solo incorpora las ventas nuevas de ese periodo.

Ejemplo: Presencial registra `2611 = 12` con entrega en vaso; posteriormente registra `2611 = 18` con entrega en botella. El resultado es `2611 × 12` y `2768 × 6`, porque la segunda boleta aporta `18 - 12 = 6`. Después de calcular cada vía por separado, el reporte final sí suma los resultados de Presencial, Kio 1, Kio 2 y Ventas online.

Para actualizar una base existente con los nombres actuales, ejecute `ACTUALIZAR_VIAS_DE_VENTA.bat`.
