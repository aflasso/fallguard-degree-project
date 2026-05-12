# Proceso de Entrenamiento — Modelo de Detección de Caídas

Pipeline completo: **Dataset LE2I → Preprocesamiento → YOLO-pose → LSTM → Evaluación**

---

## Visión general

El sistema de detección usa dos modelos en cadena:

1. **YOLO11x-pose (extracción de keypoints)** — modelo preentrenado en COCO usado directamente, sin fine-tuning. Detecta personas y extrae los 17 landmarks del esqueleto COCO en una sola pasada.
2. **LSTM (clasificación de secuencias)** — entrenado para clasificar ventanas de 20 frames en tres clases: Normal, Caída en progreso y Post-caída.

```
Video → YOLO-pose (keypoints por frame) → ventana deslizante 20 frames → LSTM → clase
```

---

## 1. Dataset: LE2I DIJON UMR6306

- **Fuente:** LE2I DIJON UMR6306
- **Resolución:** 320×240 px | **FPS:** 25
- **Subconjuntos usados:** `Coffee_room`, `Home_room`, `Lecture_room`, `Office`
- **Total:** 70 videos con anotaciones de inicio y fin de caída

**Citación requerida:**
> I. Charfi et al., "Optimised spatio-temporal descriptors for real-time fall detection", JEI, Vol. 22, Issue 4, 2013.

### Estructura original del dataset

Cada subconjunto tiene:
```
nombre_carpeta/
├── Videos/          ← archivos .avi
└── Annotation_files/
    ├── video (1).txt
    └── ...
```

Cada `.txt` tiene en su cabecera el frame de inicio y fin de caída, seguido de filas con bounding box por frame. Las etiquetas originales no son consistentes entre subconjuntos.

---

## 2. Preprocesamiento de anotaciones

**Script:** [Modelo/LSTM/Data/Le2i/convert_annotations.py](LSTM/Data/Le2i/convert_annotations.py)

El script convierte los `.txt` originales a CSVs con un esquema de 3 clases uniforme:

| Label | Significado | Condición |
|-------|-------------|-----------|
| `-1`  | Actividad normal | `frame < frame_inicio_caida` |
| `0`   | Caída en progreso | `frame_inicio ≤ frame ≤ frame_fin` |
| `1`   | Post-caída / persona en el piso | `frame > frame_fin_caida` |

Si las dos primeras líneas del `.txt` son ambas `0` (video sin caída), todos los frames quedan como `-1`.

**Salida:** `nombre_carpeta/annotations_csv/video (N).csv` con columnas `frame, label`.

```bash
python convert_annotations.py --input_dir "Coffee_room/Annotation_files"
```

---

## 3. Extracción de keypoints con YOLO-pose

**Script:** [Modelo/LSTM/Data/Le2i/extract_keypoints_yolo_pose.py](LSTM/Data/Le2i/extract_keypoints_yolo_pose.py)

Reemplaza el pipeline original MediaPipe por un único modelo YOLO-pose (`yolo11x-pose.pt`), simplificando la cadena y manteniendo compatibilidad de nombres de columna.

### Pipeline por video

1. Carga el CSV de anotaciones (`annotations_csv/video (i).csv`)
2. Abre el video correspondiente (`Videos/video (i).avi`)
3. Por cada frame: YOLO-pose detecta personas y extrae keypoints en una sola pasada
4. Se toma la detección con mayor confianza de bounding box (`best_idx = argmax(conf)`)
5. Extrae 17 landmarks COCO × (x, y) = **34 valores** por frame
6. Coordenadas normalizadas a `[0, 1]` dividiendo entre ancho/alto del frame
7. Si YOLO no detecta nada → fila con `NaN`

### Mapeo COCO → nombres de columna

| COCO idx | Columna CSV | Parte del cuerpo |
|----------|-------------|------------------|
| 0  | kp_0  | Nariz |
| 1  | kp_1  | Ojo izquierdo |
| 2  | kp_2  | Ojo derecho |
| 3  | kp_7  | Oreja izquierda |
| 4  | kp_8  | Oreja derecha |
| 5  | kp_11 | Hombro izquierdo |
| 6  | kp_12 | Hombro derecho |
| 7  | kp_13 | Codo izquierdo |
| 8  | kp_14 | Codo derecho |
| 9  | kp_15 | Muñeca izquierda |
| 10 | kp_16 | Muñeca derecha |
| 11 | kp_23 | Cadera izquierda |
| 12 | kp_24 | Cadera derecha |
| 13 | kp_25 | Rodilla izquierda |
| 14 | kp_26 | Rodilla derecha |
| 15 | kp_27 | Tobillo izquierdo |
| 16 | kp_28 | Tobillo derecho |

**Salida:** `keypoints_csv/video (i).csv` — columnas: `frame, label, kp_0_x, kp_0_y, ..., kp_28_y`

```bash
python extract_keypoints_yolo_pose.py \
    --dataset_dir  "Coffee_room" \
    --model_path   "yolo11x-pose.pt" \
    --conf         0.3 \
    --device       cuda:0
```

---

## 4. Construcción de secuencias para el LSTM

**Notebook (celda 0):** [Modelo/LSTM/Data/Le2i/train_lstm.ipynb](LSTM/Data/Le2i/train_lstm.ipynb)

### 5.1 Parámetros de ventana

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| `WINDOW` | 20 | Frames por secuencia |
| `STRIDE` | 10 | Paso entre ventanas (overlap del 50%) |
| `MIN_VALID` | 0.7 | Mínimo de frames con keypoints válidos (sin NaN) |
| `FEATURE_MODE` | `coco_xy_vel` | Tipo de features a construir |

### 5.2 Features construidas (`coco_xy_vel`)

Por cada ventana de 20 frames se calculan:
- **34 valores:** coordenadas x, y de los 17 keypoints COCO
- **34 valores de velocidad:** diferencia frame a frame de x, y

**Total: 68 features por frame × 20 frames = tensor (20, 68) por secuencia**

### 5.3 Manejo de NaN

Los frames sin detección YOLO tienen coordenadas `NaN`. Se aplica interpolación lineal columna a columna. Si toda la columna es NaN, se rellena con `0.0`.

### 5.4 Etiqueta de la ventana

Se asigna la etiqueta de clase mayoritaria de los 20 frames de la ventana.

### 5.5 Datasets usados para entrenamiento

```python
KEYPOINTS_DIRS = [
    "Coffee_room/keypoints_yolo",
    "Home_room/keypoints_yolo",
    "Fall_vision/f_raw_s_1/keypoints",
]
```

> Los subconjuntos `Lecture_room` y `Office` se reservaron exclusivamente para evaluación final (datos no vistos durante entrenamiento).

### 5.6 Distribución final

| Clase | Ventanas | % |
|-------|----------|---|
| Normal (-1) | 3 046 | 49.6% |
| Caída (0) | 2 471 | 40.2% |
| Post-caída (1) | 625 | 10.2% |
| **Total** | **6 142** | — |

**Salida:** `lstm_data/sequences.npy` (shape: `6142, 20, 69`), `labels.npy`, `meta.csv`

> Nota: el shape muestra 69 en lugar de 68 porque en la ejecución final se incluyó una feature adicional experimental.

---

## 5. Split train / val / test

El split se realiza **por video** para evitar data leakage (ventanas del mismo video no pueden aparecer en train y test simultáneamente).

| Split | Ventanas | Videos |
|-------|----------|--------|
| Train | 4 185 | 259 |
| Val   | 1 189 | 75 |
| Test  |   768 | 38 |

División: **70% train / 20% val / 10% test** sobre videos únicos.

---

## 6. Arquitectura del LSTM

```python
FallLSTM(
    input_size  = 68,   # features por frame
    hidden_size = 128,
    num_layers  = 2,
    num_classes = 3,    # Normal / Caída / Post-caída
    dropout     = 0.3,
)
```

- Entrada: `(batch, 20, 68)` — 20 timesteps, 68 features
- LSTM procesa la secuencia y toma el **último timestep** como representación
- Dropout (0.3) antes de la capa fully-connected final
- Salida: logits de 3 clases

**Parámetros entrenables: 233,859**

---

## 7. Entrenamiento

**Notebook:** [models_candidates/hardvard_le2i_yolo_sensible/train_lstm.ipynb](LSTM/Data/Le2i/models_candidates/hardvard_le2i_yolo_sensible/train_lstm.ipynb)

### Configuración

| Hiperparámetro | Valor |
|----------------|-------|
| Épocas | 50 (completas, sin early stopping) |
| Batch size | 32 |
| Learning rate | 1e-3 |
| Optimizador | Adam |
| Loss | CrossEntropyLoss con class weights |
| Early stopping | patience=10 (no se activó) |
| LR scheduler | ReduceLROnPlateau (patience=5, factor=0.5) |

### Manejo del desbalance de clases

Se usa `WeightedRandomSampler` en el DataLoader de entrenamiento para que cada clase tenga igual probabilidad de ser muestreada. La función de pérdida también recibe pesos inversos a la frecuencia de cada clase:

| Clase | Weight |
|-------|--------|
| Normal (-1) | 0.445 |
| Caída (0) | 0.514 |
| Post-caída (1) | 2.041 |

### Curva de entrenamiento

El modelo completó las 50 épocas sin activar early stopping. El mejor `val_loss` registrado fue **0.0532** (época 35 aproximadamente).

| Época | Train loss | Train acc | Val loss | Val acc |
|-------|------------|-----------|----------|---------|
| 1  | 0.4691 | 0.683 | 0.3814 | 0.864 |
| 5  | 0.1494 | 0.918 | 0.1702 | 0.929 |
| 10 | 0.1073 | 0.948 | 0.1805 | 0.920 |
| 15 | 0.0705 | 0.960 | 0.1078 | 0.943 |
| 20 | 0.0518 | 0.969 | 0.1132 | 0.939 |
| 25 | 0.0406 | 0.979 | 0.0829 | 0.955 |
| 30 | 0.0357 | 0.978 | 0.0908 | 0.953 |
| 35 | 0.0394 | 0.979 | 0.0616 | 0.963 |
| 40 | 0.0337 | 0.980 | 0.0704 | 0.964 |
| 45 | 0.0291 | 0.984 | 0.0723 | 0.965 |
| 50 | 0.0222 | 0.989 | 0.0635 | 0.961 |

La loss de validación convergió suavemente desde época 25 en adelante, sin señales de sobreajuste severo. La brecha entre train acc (0.989) y val acc (0.961) al final es pequeña, lo que indica buena generalización sobre el conjunto de validación.

### Checkpoints guardados

- `lstm_data/best_model.pt` — pesos del epoch con menor val_loss (época ~35)
- `lstm_data/fall_lstm_final.pt` — checkpoint completo con hiperparámetros y label map

### Evaluación en test set (videos no vistos en entrenamiento ni validación)

El test set contiene **768 ventanas de 38 videos**. Se evalúa con el mejor checkpoint (`best_model.pt`).

**Accuracy global: 96%**

#### Métricas por clase

| Clase | Precision | Recall | F1 | Support |
|-------|-----------|--------|----|---------|
| Normal (-1) | 1.000 | 0.957 | 0.978 | 468 |
| Caída (0) | 0.926 | 0.953 | 0.939 | 236 |
| Post-caída (1) | 0.831 | 1.000 | 0.908 | 64 |
| **Macro avg** | **0.919** | **0.970** | **0.942** | 768 |
| **Weighted avg** | **0.962** | **0.960** | **0.960** | 768 |

**Observaciones:**

- **Normal (-1):** precision perfecta (1.000) — el modelo no genera falsos positivos de caída en frames normales. El recall de 0.957 indica que un pequeño porcentaje de frames normales se clasifican erróneamente como otra clase.
- **Caída (0):** buen balance entre precision (0.926) y recall (0.953). Los falsos negativos restantes corresponden principalmente a caídas de corta duración o con keypoints parciales.
- **Post-caída (1):** recall perfecto (1.000) — el modelo identifica todos los frames de persona en el piso. La precision más baja (0.831) refleja que algunos frames de caída activa se clasifican como post-caída, lo cual es aceptable dado que ambas clases implican detección del evento.

---

## 8. Evaluación por eventos sobre videos no vistos

**Script:** [Modelo/LSTM/Data/Le2i/evaluate_videos.py](LSTM/Data/Le2i/evaluate_videos.py)

La evaluación no se hace frame a frame sino **por evento de caída**, que es más representativa para el caso de uso real.

### Lógica de conteo de eventos

Un "evento" es un grupo de frames consecutivos con predicción de caída, separados por al menos `MIN_SILENCE` frames sin caída:

- Video `Fall` con N eventos → 1 TP + (N-1) FP
- Video `Fall` con 0 eventos → 1 FN
- Video `NFall` con N eventos → N FP
- Video `NFall` con 0 eventos → 1 TN

### Parámetros de evaluación usados

| Parámetro | Valor |
|-----------|-------|
| `conf_yolo` | 0.8 |
| `conf_lstm` | 0.7 |
| `min_frames` | 3 |
| `min_silence` | 10 |

### Resultados sobre Lecture_room y Office (no vistos en entrenamiento)

| Dataset | Precision | Recall | F1 |
|---------|-----------|--------|----|
| Lecture_room | 0.8571 | 0.8571 | 0.8571 |
| Office | 0.8421 | 0.9412 | 0.8889 |
| **Micro avg** | **0.8485** | **0.9032** | **0.8750** |
| **Macro avg** | **0.8496** | **0.8992** | **0.8730** |

```bash
python evaluate_videos.py \
    --dataset_dirs "Lecture_room" "Office" \
    --model_path   "lstm_data/fall_lstm_final.pt" \
    --yolo_path    "yolo11x-pose.pt" \
    --conf         0.8 \
    --conf_lstm    0.7 \
    --min_frames   3 \
    --min_silence  10
```

---

## 9. Modelo final para producción

El modelo `fall_lstm_final.pt` se guarda con todos los metadatos necesarios para cargarlo sin hardcodear hiperparámetros:

```python
checkpoint = {
    "model_state_dict": ...,
    "hyperparams": {
        "input_size":  68,
        "hidden_size": 128,
        "num_layers":  2,
        "num_classes": 3,
        "dropout":     0.3,
        "window":      20,
    },
    "label_map":   {-1: 0, 0: 1, 1: 2},
    "label_names": ["Normal (-1)", "Caída (0)", "Post-caída (1)"],
}
```

El módulo local lo carga en `infrastructure/detector/lstm_model.py` y lo combina con YOLO-pose en `infrastructure/detector/yolo_pose.py`.

---

## 10. Inferencia en tiempo real

**Script:** [Modelo/LSTM/Data/Le2i/realtime_inference_yolo.py](LSTM/Data/Le2i/realtime_inference_yolo.py)

Pipeline por frame en producción:

1. Captura frame de cámara o video
2. YOLO-pose detecta persona y extrae keypoints normalizados
3. Se mantiene buffer circular de los últimos 20 frames (`deque(maxlen=20)`)
4. Al llenarse el buffer, se calcula velocidad y se pasa al LSTM
5. LSTM retorna probabilidades de las 3 clases vía `softmax`
6. Lógica de confirmación:
   - Pred == 1 (Caída): agrega `prob_caida` al deque de confirmación (`maxlen=3`)
   - Si `len(deque)==3` y `mean(deque) >= conf_lstm (0.7)` → **caída confirmada**
   - Si pasan `alert_cooldown (30)` frames consecutivos sin caída → alerta desactivada

```bash
python realtime_inference_yolo.py \
    --model_path  "lstm_data/fall_lstm_final.pt" \
    --yolo_path   "yolo11x-pose.pt" \
    --source      0 \
    --conf        0.8 \
    --conf_lstm   0.7 \
    --min_frames  3
```

---

## 11. Estructura de archivos del Modelo/

```
Modelo/
├── checkpoints/
│   ├── td-hm_hrnet-w48_8xb32-210e_coco-256x192.pth   ← checkpoint HRNet (exploración previa)
│   └── td-hm_hrnet-w48_8xb32-210e_coco-256x192.py
│
├── LSTM/
│   └── Data/
│       └── Le2i/
│           ├── README.md                        ← descripción del preprocesamiento
│           ├── convert_annotations.py           ← txt → csv de anotaciones
│           ├── extract_keypoints_yolo_pose.py   ← extracción de keypoints por frame
│           ├── train_lstm.ipynb                 ← notebook de entrenamiento
│           ├── evaluate_videos.py               ← evaluación por evento
│           ├── realtime_inference_yolo.py       ← inferencia en tiempo real
│           ├── debug_visual.py                  ← visualización de keypoints
│           ├── Coffee_room/  Home_room/  Office/  Lecture_room/
│           ├── lstm_data/
│           │   ├── sequences.npy                ← (6142, 20, 69)
│           │   ├── labels.npy
│           │   ├── meta.csv
│           │   ├── best_model.pt
│           │   └── fall_lstm_final.pt           ← modelo final de producción
│           ├── models_candidates/               ← experimentos anteriores
│           │   ├── generalizado_le2i_fallv/
│           │   ├── hardvard_le2i/
│           │   ├── hardvard_le2i_yolo_estrict/
│           │   ├── hardvard_le2i_yolo_sensible/ ← modelo seleccionado
│           │   └── todos_urfall_le2i_fallv/
│           └── yolo11x-pose.pt                  ← modelo YOLO-pose para extracción
│
└── Yolo/                                        ← carpeta de exploración, no forma parte del pipeline
```

---

## 12. Decisiones de diseño relevantes

**¿Por qué YOLO-pose en lugar de YOLO + MediaPipe?**
Simplifica la cadena a un solo modelo: detección y extracción de keypoints en una sola pasada, reduciendo latencia y eliminando una dependencia externa.

**¿Por qué 3 clases y no 2 (caída / no caída)?**
La clase post-caída (`1`) captura el estado de persona en el piso que visualmente es diferente a la caída en progreso. Sin esta clase el modelo confundiría post-caída con actividad normal una vez terminado el movimiento.

**¿Por qué el split por video y no por frame?**
Ventanas consecutivas del mismo video son altamente correlacionadas. Un split por frame contaminaría train con información de los mismos instantes que aparecen en test, inflando artificialmente las métricas.

**¿Por qué `Lecture_room` y `Office` como conjunto de evaluación?**
Son los subconjuntos más distintos en iluminación y disposición del espacio respecto a `Coffee_room` y `Home_room`. Usarlos solo en evaluación da una estimación más honesta de la generalización del modelo.
