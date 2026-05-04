# Sistema de Detección de Caídas

Sistema distribuido para detección automática de caídas en hogares, con notificación en tiempo real al usuario a través de una aplicación móvil.

---

## Arquitectura general

```
[Cámara]
   ↓
[Módulo local (PC en el hogar)]
   ├── Detección: YOLO-pose + LSTM
   ├── Buffer circular de video
   ├── Lógica de evento (min_frames, conf_lstm, cooldown)
   └── WebSocket client
          ↕ alertas / clips / heartbeat / config
[Servidor central (cloud)]
   ├── Registro y estado de módulos
   ├── Gestión de usuarios
   ├── Reenvío de alertas → App móvil (push notification)
   └── Referencias a clips (URLs del bucket)
          ↓ push notifications
[App móvil]
   ├── Recibe alertas de caída
   ├── Visualiza clips del evento
   ├── Ve estado del módulo (conectado/desconectado)
   └── Vincula módulo via QR
          ↑ HTTP REST
[Bucket cloud (S3 / Firebase Storage / Cloudinary)]
   └── Almacena clips de video de los eventos
```

---

## Módulo local

### Responsabilidades
- Capturar video desde cámara física conectada al PC
- Detectar personas con YOLO-pose
- Extraer keypoints y construir features para el LSTM
- Confirmar eventos de caída con lógica de ventana deslizante
- Grabar clip con contexto antes/después de la caída
- Subir clip al bucket cloud via presigned URL
- Comunicarse con el servidor central via WebSocket
- Guardar alertas localmente si no hay conexión y reenviarlas al reconectar

### Modelo de detección

| Parámetro | Valor | Descripción |
|---|---|---|
| Arquitectura | LSTM | Clasificación de secuencias temporales |
| Ventana | 20 frames | Contexto temporal por predicción |
| Features | 68 | x,y de 17 keypoints COCO + velocidad x,y |
| Clases | 3 | Normal / Cayendo / Post-caída |
| `conf_yolo` | 0.8 | Confianza mínima YOLO para detectar persona |
| `conf_lstm` | 0.7 | Confianza media mínima del LSTM para confirmar evento |
| `min_frames` | 3 | Frames consecutivos mínimos para confirmar caída |
| `alert_cooldown` | 30 frames | Frames sin caída para desactivar alerta activa |

### Keypoints utilizados (COCO → nomenclatura MediaPipe)

| COCO idx | Columna CSV | Parte del cuerpo |
|---|---|---|
| 0 | kp_0 | Nariz |
| 1 | kp_1 | Ojo izquierdo |
| 2 | kp_2 | Ojo derecho |
| 3 | kp_7 | Oreja izquierda |
| 4 | kp_8 | Oreja derecha |
| 5 | kp_11 | Hombro izquierdo |
| 6 | kp_12 | Hombro derecho |
| 7 | kp_13 | Codo izquierdo |
| 8 | kp_14 | Codo derecho |
| 9 | kp_15 | Muñeca izquierda |
| 10 | kp_16 | Muñeca derecha |
| 11 | kp_23 | Cadera izquierda |
| 12 | kp_24 | Cadera derecha |
| 13 | kp_25 | Rodilla izquierda |
| 14 | kp_26 | Rodilla derecha |
| 15 | kp_27 | Tobillo izquierdo |
| 16 | kp_28 | Tobillo derecho |

### Lógica de confirmación de caída

El sistema no dispara alerta en el primer frame con predicción de caída. Usa una ventana deslizante de `min_frames` sobre las confianzas del LSTM:

```
Por cada frame con pred==1:
  → Agrega prob_caida a deque(maxlen=3)
  → Si len(deque) == 3 Y mean(deque) >= 0.7:
      → Confirmar caída → grabar clip → subir → alertar

Por cada frame con pred!=1:
  → Si no hay alerta activa: limpiar deque
  → Si hay alerta activa: incrementar silence_counter
      → Si silence_counter >= 30: desactivar alerta
```

### Clip de video
- El módulo mantiene un buffer circular de los últimos ~3s de video en memoria
- Al confirmar una caída graba: ~3s antes + ~2s después del evento
- El módulo solicita una presigned URL al servidor, sube el clip directamente al bucket
- Solo la URL pública se envía al servidor (el servidor nunca toca el video)

### Métricas de validación del modelo

Evaluado sobre conjuntos **Lecture_room** y **Office** del dataset LE2I (videos no vistos durante entrenamiento ni validación):

| Dataset | Precision | Recall | F1 |
|---|---|---|---|
| Lecture_room | 0.8571 | 0.8571 | 0.8571 |
| Office | 0.8421 | 0.9412 | 0.8889 |
| **Micro avg** | **0.8485** | **0.9032** | **0.8750** |
| **Macro avg** | **0.8496** | **0.8992** | **0.8730** |

Evaluación con `conf_yolo=0.8`, `conf_lstm=0.7`, `min_frames=3`, `min_silence=10`.

---

## Arquitectura interna del módulo local

El módulo sigue **arquitectura limpia (Clean Architecture)** con tres capas y un modelo de **3 threads** comunicados por colas.

### Estructura de carpetas

```
fall_detection_module/
├── domain/
│   ├── entities.py              ← FallEvent, Alert, CameraInfo, FallPrediction
│   ├── value_objects.py         ← FeatureSchema, Keypoints, KeypointsSequence
│   └── fall_service.py          ← reglas puras de negocio (ventana deslizante)
│
├── application/
│   ├── ports/
│   │   ├── alert_queue.py       ← interfaz: cola local de alertas pendientes
│   │   ├── alert_sender.py      ← interfaz: send(alert) -> bool
│   │   ├── camera.py            ← interfaz: read() -> frame
│   │   ├── camera_scanner.py    ← interfaz: scan() -> List[CameraInfo]
│   │   ├── clip_recorder.py     ← interfaz: add_frame(), record()
│   │   ├── clip_storage.py      ← interfaz: upload(clip) -> URL
│   │   ├── fall_predictor.py    ← interfaz: predict(sequence) -> FallPrediction
│   │   └── keypoint_extractor.py← interfaz: extract(frame) -> Keypoints
│   └── use_cases/
│       ├── detect_fall.py       ← orquesta extractor + predictor + fall_service
│       ├── send_alert.py        ← orquesta clip_recorder + storage + sender
│       └── manage_camera.py     ← listar y cambiar cámara
│
├── infrastructure/
│   ├── detector/
│   │   ├── yolo_pose.py         ← implementa KeypointExtractor (YOLO11x-pose)
│   │   └── lstm_model.py        ← implementa FallPredictor (PyTorch LSTM)
│   ├── video/
│   │   ├── opencv_camera.py     ← implementa Camera (cv2.VideoCapture)
│   │   ├── opencv_camera_scanner.py ← implementa CameraScanner
│   │   ├── active_camera.py     ← contenedor thread-safe para cambio de cámara
│   │   └── clip_recorder.py     ← implementa ClipRecorder (buffer circular + mp4)
│   ├── comms/
│   │   ├── ws_client.py         ← implementa AlertSender (WebSocket)
│   │   └── s3_uploader.py       ← implementa ClipStorage (presigned URL → S3)
│   └── storage/
│       └── local_queue.py       ← implementa AlertQueue (JSON en disco)
│
├── tests/
│   ├── test_domain.py           ← tests unitarios del dominio
│   └── test_integration.py      ← tests de integración YOLO + LSTM + pipeline
│
├── config.py                    ← configuración central (lee desde .env)
├── main.py                      ← punto de entrada, orquesta los 3 threads
├── pyproject.toml               ← definición del paquete
└── .env                         ← variables de entorno (no subir a git)
```

### Capas

| Capa | Responsabilidad | Dependencias |
|---|---|---|
| `domain` | Entidades, value objects y reglas de negocio puras | Ninguna |
| `application` | Casos de uso y puertos (interfaces) | Solo domain |
| `infrastructure` | Implementaciones concretas (YOLO, LSTM, S3, WebSocket, OpenCV) | Application + librerías externas |

### Threads y colas

```
Thread 1 — Detección (loop principal)
    captura frame → add_frame (buffer circular)
    → YOLO extrae keypoints → buffer LSTM
    → LSTM predice → FallDetectionService evalúa
    caída confirmada → clip_queue

Thread 2 — Uploader
    escucha clip_queue
    graba clip con contexto antes/después
    solicita presigned URL al servidor (HTTP)
    sube clip directamente al bucket S3
    → alert_queue con URL final

Thread 3 — WebSocket
    mantiene conexión con el servidor
    envía heartbeat cada 30s
    envía alertas de alert_queue
    recibe mensajes (set_camera, config_update)
    sin conexión → guarda alertas en local_queue (disco)
    al reconectar → vacía local_queue y reenvía alertas
```

### Colas internas

| Cola | De | A | Contenido |
|---|---|---|---|
| `clip_queue` | T1 Detección | T2 Uploader | FallEvent con frames del buffer |
| `alert_queue` | T2 Uploader | T3 WebSocket | Alert con clip_url |
| `local_queue` | T3 WebSocket | T3 WebSocket | Alertas pendientes en disco (JSON) |

### Estados del módulo

| Estado | Descripción |
|---|---|
| `waiting_camera` | Conectado al servidor, sin cámara seleccionada |
| `running` | Cámara activa, detectando caídas |
| `disconnected` | Sin conexión al servidor, detección activa, alertas en cola local |

---

## Configuración

Todos los parámetros se configuran en el archivo `.env`:

```env
# Servidor
SERVER_WS_URL=ws://localhost:8000/ws
SERVER_HTTP_URL=http://localhost:8000

# Modelos
YOLO_MODEL_PATH=models/yolo11x-pose.pt
LSTM_MODEL_PATH=models/fall_lstm_final.pt
DEVICE=cuda:0

# Detección
CONF_YOLO=0.8
CONF_LSTM=0.7
MIN_FRAMES=3
ALERT_COOLDOWN=30

# Clip de video
CLIPS_DIR=data/clips
CONTEXT_BEFORE=75
CONTEXT_AFTER=50
VIDEO_FPS=25.0

# Cola local
LOCAL_QUEUE_PATH=data/pending_alerts.json

# Logging
LOG_LEVEL=INFO
```

---

## Instalación y uso

```cmd
cd fall_detection_module
pip install -e .
python main.py
```

Para correr los tests:
```cmd
pytest tests/ -v
```

---

## Protocolo de comunicación

### Módulo → Servidor (WebSocket)

#### Conexión inicial
```json
{
  "type": "module_connect",
  "module_id": "uuid-del-modulo",
  "version": "1.0.0",
  "cameras": [
    {"id": 0, "name": "Camara integrada"},
    {"id": 1, "name": "Camara USB"}
  ]
}
```

#### Heartbeat (cada 30 segundos)
```json
{
  "type": "heartbeat",
  "module_id": "uuid-del-modulo",
  "timestamp": "2026-04-18T14:30:00Z"
}
```

#### Alerta de caída
```json
{
  "type": "fall_alert",
  "module_id": "uuid-del-modulo",
  "timestamp": "2026-04-18T14:30:00Z",
  "confidence": 0.87,
  "clip_id": "uuid-del-clip",
  "clip_url": "https://storage.example.com/clips/clip_uuid.mp4"
}
```

#### Confirmación de configuración recibida
```json
{
  "type": "config_ack",
  "module_id": "uuid-del-modulo",
  "config_version": 2
}
```

---

### Servidor → Módulo (WebSocket)

#### Confirmación de conexión
```json
{
  "type": "connected",
  "module_id": "uuid-del-modulo",
  "config": {
    "version": 2,
    "conf_yolo": 0.8,
    "conf_lstm": 0.7,
    "min_frames": 3,
    "alert_cooldown": 30
  }
}
```

#### Presigned URL para subir clip
```json
{
  "type": "upload_url",
  "clip_id": "uuid-del-clip",
  "presigned_url": "https://bucket.s3.amazonaws.com/clips/uuid.mp4?X-Amz-Signature=...",
  "expires_in": 300
}
```

#### Cambiar cámara activa
```json
{
  "type": "set_camera",
  "camera_id": 1
}
```

#### Actualización de configuración
```json
{
  "type": "config_update",
  "config": {
    "version": 3,
    "conf_yolo": 0.8,
    "conf_lstm": 0.65,
    "min_frames": 3,
    "alert_cooldown": 30
  }
}
```

---

### App móvil → Servidor (HTTP REST)

| Método | Endpoint | Descripción |
|---|---|---|
| POST | `/api/modules/link` | Vincular módulo escaneando QR |
| GET | `/api/alerts` | Historial de alertas del usuario |
| GET | `/api/alerts/:id/clip` | Ver clip de una caída específica |
| GET | `/api/modules/status` | Estado del módulo (conectado/desconectado) |

---

### Servidor → App móvil (Push notifications)

#### Caída detectada
```json
{
  "title": "Caída detectada",
  "body": "Se detectó una caída en tu hogar",
  "data": {
    "alert_id": "uuid-alerta",
    "timestamp": "2026-04-18T14:30:00Z",
    "clip_url": "https://storage.example.com/clips/clip_uuid.mp4"
  }
}
```

#### Módulo desconectado
```json
{
  "title": "Módulo desconectado",
  "body": "No se ha podido contactar tu dispositivo de detección",
  "data": {
    "module_id": "uuid-del-modulo",
    "last_seen": "2026-04-18T14:30:00Z"
  }
}
```

---

## Vinculación de módulo con usuario

1. El módulo arranca y genera o carga su UUID único (persistido en `data/module_id.txt`)
2. El módulo muestra su UUID como QR (en pantalla o impreso)
3. El usuario escanea el QR desde la app
4. La app envía `POST /api/modules/link` con `{user_id, module_id}`
5. El servidor vincula el módulo al usuario
6. A partir de ese momento las alertas del módulo se dirigen a ese usuario

---

## Manejo de desconexión

- El módulo envía heartbeat cada 30 segundos
- Si el servidor no recibe heartbeat en 90 segundos (3 intervalos), marca el módulo como desconectado y notifica al usuario via push notification
- Si el módulo detecta una caída sin conexión, guarda la alerta en `data/pending_alerts.json`
- Al reconectar, el módulo envía automáticamente todas las alertas pendientes

---

## Scripts de entrenamiento y evaluación

| Script | Descripción |
|---|---|
| `extract_keypoints_yolo_pose.py` | Extrae keypoints por frame de videos del dataset LE2I usando YOLO-pose |
| `build_sequences.py` | Construye secuencias de features para entrenamiento del LSTM |
| `realtime_inference.py` | Inferencia en tiempo real desde cámara o video con visualización |
| `evaluate_videos.py` | Evalúa el modelo sobre carpetas Fall/NFall y genera métricas precision/recall/F1 |