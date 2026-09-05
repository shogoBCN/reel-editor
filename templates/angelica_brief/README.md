# Cómo entregar un reel (Dra. Angélica)

Esta carpeta es la **plantilla humana**. No tienes que tocar YAML ni código.

**La mejor herramienta:** el archivo Excel `plantilla_reel_angelica.xlsx`. Ábrelo en Excel, o súbelo a Drive → Abrir con → Hojas de cálculo de Google. (CSV = las mismas pestañas sueltas; el editor puede leer las dos.)

Las **imágenes se pegan en la hoja**, columna `imagen` (Insertar → imagen en la celda). El editor las saca al importar el `.xlsx`. También puedes mandar PNG sueltos con el nombre de `archivo_imagen`.

**¿Por qué una hoja y no un Doc?** Los tiempos y lados son una tabla. Un Doc es cómodo para pegar capturas, pero el editor no puede leerlo. Las fotos van **en la columna imagen** de la misma hoja.

---

## La regla del reloj (léela dos veces)

Todos los tiempos son el reloj de **tu grabación original** — el video que filmaste, incluyendo los segundos de silencio o toma fallida al inicio.

**No** es el reloj del reel ya recortado de Instagram. El recorte (`cortar_inicio`) se aplica después.

Ejemplos:

| Tú escribes | Significa |
|-------------|-----------|
| `0:24` o `24` | Segundo 24 de *tu* video |
| `0:24.5` | 24 segundos y medio |
| `1:29.5` | 1 minuto 29.5 segundos |
| `4.0` en `cortar_inicio` | Quitar los primeros 4 segundos de silencio / arranque falso |

Si dos stickers se superponen (frutero a la **derecha** y susto a la **izquierda**), cada uno es **una fila** con su propio inicio y fin. La altura es la misma sola.

---

## Qué enviar cada vez

1. El video de cabeza (mejor vertical 9:16).
2. Esta hoja, llena.
3. Las imágenes: pégalas en la columna `imagen` de la pestaña Imagenes_y_tiempos, **o** una carpeta de PNG con el mismo nombre que `archivo_imagen`.
4. Opcional: una nota de voz. Si lo escribes claro en **notas_edicion**, basta.

Nombra los archivos en español, **sin espacios**: `frutero_alto.png`. Si pegas la foto en la celda, `archivo_imagen` puede repetir ese nombre (o dejarse y se usa el `id`).

---

## Separadores (pestañas)

| Pestaña | Archivo | Qué llenas |
|---------|---------|------------|
| Proyecto | `01_proyecto.csv` | Título, dónde empieza/termina el habla, fundido |
| Imágenes y tiempos | `02_imagenes_y_tiempos.csv` | Una fila por sticker o título; fotos en columna `imagen` |
| Correcciones | `03_correcciones_transcripcion.csv` | Errores de transcripción (`lacena` → `alacena`) |
| Notas | `04_notas_edicion.csv` | Libres (sí / no hacer) |

Una quinta pestaña **Instrucciones** puede pegar este texto. El importador la ignora.

---

## `lado` (dónde se ve)

| Valor | Dónde queda |
|-------|-------------|
| `derecha` | A la derecha de la cabeza, a la altura del frutero (por defecto para fotos) |
| `izquierda` | A la izquierda de la cabeza, misma altura |
| `gancho` | Centrado, en el cielo debajo del recorte de Instagram (nombre, ENFOQUE) |

**No** pongas stickers encima de la cabeza/sombrero (parece disfraz). Los subtítulos van en el escote del saco, no sobre la cara.

---

## `tipo`

| Valor | Qué hace |
|-------|----------|
| `sticker` | Pega la foto en `imagen` (y/o `archivo_imagen`) |
| `etiqueta` | Pincel teal + texto blanco de la columna `texto` (ej. `Dra. Angélica`) |
| `enfoque` | Genera ENFOQUE INTEGRAL / Bio – Psico – Social. Sin archivo |

---

## Cómo armar la Hoja de Google (una sola vez)

**Camino corto (recomendado):** sube `plantilla_reel_angelica.xlsx` a Google Drive → clic derecho → Abrir con → Hojas de cálculo de Google. Ya trae pestañas, encabezados congelados y menús de `tipo` / `lado`.

**Camino CSV:** crea una hoja vacía e importa cada CSV como pestaña nueva.

Luego:

1. Fija la fila 1 si no quedó fija.
2. Duplica la hoja para cada reel nuevo. Renómbrala con fecha + tema.
3. Comparte la copia (con las fotos ya pegadas en la columna imagen) + el video.

Ejemplo lleno: `examples/ya_tienes/brief_sheet/` (el reel “Ya tienes”).

---

## Detalle que sí importa (más que un Word)

Para cada imagen, escribe en **qué_es** y **notas_edicion**:

- **Qué se ve** (frutero con mango/plátano/uvas, no “imagen 3”).
- **Por qué sale en ese segundo** (lo que estás diciendo).
- **Si entra después** de otra imagen (el susto se suma al frutero, no lo reemplaza).
- **Si no debe tapar** algo (cara, subtítulo, WhatsApp de la tarjeta final).
- **Si es broma / susto / dato** — el editor elige tamaño, no el tono.

Tiempos con décimas (`0:28.00`) cuando dos cosas coinciden. `0:28` está bien si no hay cruce.

La tarjeta de contacto del final **no** va en esta tabla: se pone sola al terminar el habla.

---

## Después de enviarlo

El editor corre:

```bash
python pipelines/import_brief.py --xlsx projects/<slug>/brief_sheet/<slug>.xlsx --out projects/<slug>/brief.yaml
python pipelines/reel_compose.py --project projects/<slug> --preview
```

Primero salen JPEGs de preview para afinar tiempos; el encode largo es el segundo paso.
