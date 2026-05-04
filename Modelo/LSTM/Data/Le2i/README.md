# LE2I Fall Detection Dataset — Preprocesamiento de Anotaciones

> Dataset original: **LE2I DIJON UMR6306**  
> Resolución: `320×240` · Framerate: `25 FPS`  
> Subconjuntos: `Home`, `Coffee room`, `Office`, `Lecture room`  
> 70 videos en total

---

## Citación requerida

> I. Charfi, J. Mitéran, J. Dubois, M. Atri, R. Tourki,
> *"Optimised spatio-temporal descriptors for real-time fall detection: comparison of SVM and Adaboost based classification"*,
> **Journal of Electronic Imaging (JEI)**, Vol. 22, Issue 4, pp. 17, October 2013.

---

## Estructura original del dataset

```
nombre_carpeta/
└── Annotation_files/
    ├── video (1).txt
    ├── video (2).txt
    └── ... (70 archivos)
```

### Formato de cada `video (i).txt`

```
<frame_inicio_caida>
<frame_fin_caida>
<frame_n>, <altura_bbox>, <ancho_bbox>, <centro_x>, <centro_y>, <columna_extra>
<frame_n+1>, ...
...
```

**Columnas del archivo original (por fila de frame):**

| Columna | Descripción |
|---------|-------------|
| 1 | Número de frame |
| 2 | Etiqueta original (múltiples clases) |
| 3 | Altura del bounding box |
| 4 | Ancho del bounding box |
| 5 | Coordenada X del centro del bbox |
| 6 | Coordenada Y del centro del bbox |

### Ejemplo — archivo original

```
42          ← frame donde comienza la caída
78          ← frame donde termina la caída
1, 3, 180, 95, 160, 120
2, 3, 181, 96, 161, 121
...
41, 3, 175, 94, 158, 119
42, 2, 140, 110, 162, 180   ← inicio caída
...
78, 2, 95, 130, 163, 200    ← fin caída
79, 1, 90, 132, 164, 205
...
```

> ⚠️ La etiqueta original (columna 2) varía entre datasets y no es consistente entre archivos. Por eso se descarta y se recalcula.

---

## Problema con las etiquetas originales

El dataset LE2I usa **múltiples valores de etiqueta** en la columna 2 (p. ej. `1`, `2`, `3`...) cuyo significado varía entre subconjuntos y no está estandarizado. Para entrenar un modelo LSTM se necesita un esquema uniforme de 3 clases.

---

## Conversión aplicada → `annotations_csv/`

### Nueva estructura de salida

```
nombre_carpeta/
├── Annotation_files/
│   ├── video (1).txt
│   └── ...
└── annotations_csv/          ← generado por el script
    ├── video (1).csv
    └── ...
```

### Nuevo esquema de etiquetas

| Label | Significado | Condición |
|-------|-------------|-----------|
| `-1`  | Actividad normal | `frame < frame_inicio_caida` |
| ` 0`  | Caída en progreso | `frame_inicio_caida ≤ frame ≤ frame_fin_caida` |
| ` 1`  | Post-caída / persona en el piso | `frame > frame_fin_caida` |

> **Caso especial:** si las dos primeras líneas del `.txt` son ambas `0`, o el archivo no tiene cabecera válida, **todos los frames del video se etiquetan como `-1`** (actividad completamente normal).

### Formato del CSV generado

```csv
frame,label
1,-1
2,-1
...
42,0
...
78,0
79,1
...
```

Solo se conservan las **columnas esenciales para el LSTM**: número de frame y etiqueta normalizada. Las columnas del bounding box no se incluyen porque la detección de persona se realizará con un modelo re entrenado de **YOLOv11** utlizando el dataset original y la extracción de keypoints con **MediaPipe**.

---

## Ejemplo visual del antes y después

### Antes — `video (1).txt`

```
42
78
1, 3, 180, 95, 160, 120
2, 3, 181, 96, 161, 121
39, 3, 178, 93, 157, 118
40, 3, 177, 93, 158, 118
41, 3, 175, 94, 158, 119
42, 2, 140, 110, 162, 180
60, 2, 110, 125, 163, 195
78, 2, 95, 130, 163, 200
79, 1, 90, 132, 164, 205
95, 1, 88, 133, 164, 207
```

### Después — `video (1).csv`

```csv
frame,label
1,-1
2,-1
39,-1
40,-1
41,-1
42,0
60,0
78,0
79,1
95,1
```

## Script de conversión

El script `convert_annotations.py` realiza todo el proceso automáticamente:

```bash
python convert_annotations.py --input_dir "nombre_carpeta/Annotation_files"
```

Al finalizar imprime un resumen por archivo con el conteo de frames por clase:

```
✅ video (1).txt  → video (1).csv  | frames: 200  (-1:  95, 0: 37, 1: 68)
✅ video (2).txt  → video (2).csv  | frames: 180  (-1: 180, 0:  0, 1:  0)
...
✔  Conversión completada. CSVs guardados en: nombre_carpeta/annotations_csv
```