# fall_detection_module — Contexto del proyecto

## Qué es este módulo

Módulo local que corre en un PC en el hogar. Captura video desde una cámara, detecta caídas en tiempo real usando YOLO-pose + LSTM, graba clips del evento y los sube al servidor central via WebSocket.

Sus responsabilidades son:
- Capturar video desde cámara física o archivo (modo test)
- Extraer keypoints de pose con YOLO11x-pose (pretrained, sin fine-tuning)
- Clasificar secuencias temporales con LSTM (Normal / Cayendo / Post-caída)
- Confirmar eventos de caída con lógica de ventana deslizante
- Grabar clip con contexto antes/después del evento
- Solicitar presigned URL al servidor via WebSocket y subir clip directamente a GCS
- Enviar alerta de caída al servidor via WebSocket
- Guardar alertas en cola local si no hay conexión y reenviarlas al reconectar

---

## Lugar en el sistema

```
[Cámara]
   ↓
[fall_detection_module]  ← este módulo
   ├── YOLO11x-pose → keypoints
   ├── LSTM → clasificación
   ├── Buffer circular → clip de video
   └── WebSocket client
          ↕ alertas / presigned URLs / heartbeat
[fall_detection_server]
   └── GCS (subida directa con presigned URL)
```

---

## Modelo de detección

| Parámetro | Valor | Descripción |
|---|---|---|
| Extractor | YOLO11x-pose (pretrained) | 17 keypoints COCO por frame, normalizado a [0,1] |
| Clasificador | LSTM (2 capas, hidden=128) | Secuencias de 20 frames, 68 features por frame |
| Features | `coco_xy_vel` | x,y de 17 keypoints + velocidad x,y = 68 valores |
| Clases | 3 | Normal (-1) / Cayendo (0) / Post-caída (1) |
| `conf_yolo` | 0.8 | Confianza mínima YOLO para detectar persona |
| `conf_lstm` | 0.7 | Media mínima sobre deque(3) para confirmar evento |
| `min_frames` | 3 | Frames consecutivos de caída para confirmar |
| `alert_cooldown` | 30 | Frames sin caída para desactivar alerta activa |

### Lógica de confirmación

```
Por cada frame con pred == Cayendo:
  → agrega prob_caida a deque(maxlen=3)
  → si len(deque) == 3 y mean(deque) >= conf_lstm:
      → caída confirmada → grabar clip → subir → alertar

Por cada frame con pred != Cayendo:
  → si no hay alerta activa: limpiar deque
  → si hay alerta activa: incrementar silence_counter
      → si silence_counter >= alert_cooldown: desactivar alerta
```

---

## Arquitectura interna

Clean Architecture con tres capas y modelo de **3 threads** comunicados por colas.

```
domain/       ← Entidades (FallEvent, Alert, CameraInfo) y reglas puras (FallDetectionService)
application/  ← Casos de uso (DetectFall, SendAlert, ManageCamera) y puertos (interfaces)
infrastructure/ ← Implementaciones concretas (YOLO, LSTM, OpenCV, WebSocket, GCS)
```

### Threads y colas

```
Thread 1 — Detection (loop principal)
    frame → YOLO → LSTM → FallDetectionService
    caída confirmada → clip_queue (FallEvent)

Thread 2 — Uploader
    escucha clip_queue
    graba clip (buffer circular de Thread 1)
    solicita presigned URL al servidor via WebSocket
    sube clip directamente a GCS (PUT)
    → alert_queue (Alert con clip_url)

Thread 3 — WebSocket
    mantiene conexión con el servidor
    envía alertas de alert_queue
    recibe mensajes del servidor (upload_url, set_camera, config_update)
    sin conexión → alertas van a local_queue (disco)
    al reconectar → vacía local_queue en thread separado (ReconnectFlush)
```

### Colas

| Cola | De | A | Contenido |
|---|---|---|---|
| `clip_queue` | Thread 1 | Thread 2 | `FallEvent` confirmado |
| `alert_queue` | Thread 2 | Thread 3 | `Alert` con `clip_url` lista |
| `local_queue` | Thread 3 | Thread 3 | Alertas persistidas en disco cuando no hay conexión |

---

## Flujo de subida de clip

1. Thread 2 llama a `WebSocketClient.request_upload_url(clip_id)`
2. El cliente envía `{ "type": "request_upload_url", ... }` al servidor
3. El servidor responde con `{ "type": "upload_url", "presigned_url": "...", "public_url": "..." }`
4. Thread 2 hace PUT directo a GCS con la presigned URL
5. Thread 2 pone la `Alert` con `clip_url` en `alert_queue`
6. Thread 3 envía `{ "type": "fall_alert", "clip_url": "..." }` al servidor

`request_upload_url` es **sincrónico** — bloquea Thread 2 hasta recibir respuesta o timeout (30s).
Usa polling cada 1s para detectar desconexión y fallar rápido en lugar de esperar el timeout completo.

Si el servidor responde con `upload_url_error`, se lanza `RuntimeError` y la alerta va a cola local.

---

## Autenticación WebSocket

El módulo se conecta a `ws://<host>/ws?api_key=<MODULE_API_KEY>`.

- `MODULE_API_KEY` se configura en `.env` del módulo y debe coincidir con `MODULE_API_KEY` del servidor.
- Si el key es inválido, el servidor cierra con código `4001`. El cliente detecta el código y detiene la reconexión automática.
- Si el servidor está caído o el key es correcto pero hay error de red, el cliente reintenta con backoff exponencial (1s → 2s → 4s → ... → 60s máximo).

---

## Protocolo WebSocket

### Módulo → Servidor

```jsonc
{ "type": "module_connect", "module_id": "uuid", "version": "1.0.0",
  "cameras": [{"id": 0, "name": "Camara integrada"}] }

{ "type": "heartbeat", "module_id": "uuid", "timestamp": "2026-04-12T14:30:00Z" }

{ "type": "request_upload_url", "module_id": "uuid", "clip_id": "uuid-clip" }

{ "type": "fall_alert", "module_id": "uuid", "timestamp": "...",
  "confidence": 0.87, "clip_id": "uuid-clip", "clip_url": "https://..." }

{ "type": "config_ack", "module_id": "uuid", "config_version": 2 }
```

### Servidor → Módulo

```jsonc
{ "type": "connected", "module_id": "uuid" }

{ "type": "upload_url", "clip_id": "uuid-clip",
  "presigned_url": "https://storage.googleapis.com/...",
  "public_url": "https://storage.googleapis.com/...", "expires_in": 300 }

{ "type": "upload_url_error", "clip_id": "uuid-clip", "error": "descripción" }

{ "type": "set_camera", "camera_id": 1 }

{ "type": "config_update", "config": { "version": 3, ... } }
```

---

## Configuración

Variables de entorno (ver `.env.template`):

| Variable | Default | Descripción |
|---|---|---|
| `SERVER_WS_URL` | `ws://localhost:8000/ws` | URL WebSocket del servidor |
| `SERVER_HTTP_URL` | `http://localhost:8000` | URL HTTP del servidor (no usado actualmente) |
| `MODULE_API_KEY` | `""` | API key para autenticar la conexión WebSocket |
| `YOLO_MODEL_PATH` | `models/yolo11x-pose.pt` | Ruta al modelo YOLO de pose |
| `LSTM_MODEL_PATH` | `models/fall_lstm_final.pt` | Ruta al modelo LSTM entrenado |
| `DEVICE` | `cpu` | Dispositivo de inferencia (`cpu`, `cuda:0`, ...) |
| `CONF_YOLO` | `0.8` | Confianza mínima YOLO |
| `CONF_LSTM` | `0.7` | Confianza mínima LSTM para confirmar caída |
| `MIN_FRAMES` | `3` | Frames consecutivos para confirmar caída |
| `ALERT_COOLDOWN` | `30` | Frames de cooldown tras alerta |
| `CLIPS_DIR` | `data/clips` | Directorio local de clips grabados |
| `CONTEXT_BEFORE` | `75` | Frames antes de la caída (~3s a 25fps) |
| `CONTEXT_AFTER` | `50` | Frames después de la caída (~2s a 25fps) |
| `CAMERA_SOURCE` | `0` | Índice de cámara o ruta a video (modo test) |
| `LOCAL_QUEUE_PATH` | `data/pending_alerts.json` | Cola local persistida en disco |
| `LOG_LEVEL` | `INFO` | Nivel de logging |

El `MODULE_ID` se genera automáticamente en el primer arranque y se persiste en `data/module_id.txt`.

---

## Cómo correr el módulo

```bash
cd fall_detection_module
python -m venv venv
venv\Scripts\activate          # Windows
pip install -e ".[dev]"
cp .env.template .env          # completar variables
python main.py
```

---

## Estructura de archivos

```
fall_detection_module/
├── main.py                          ← orquesta los 3 threads, wiring de dependencias
├── config.py                        ← variables de entorno, MODULE_ID persistido
├── pyproject.toml
├── .env / .env.template
├── data/
│   ├── module_id.txt                ← UUID del módulo (generado en primer arranque)
│   ├── clips/                       ← clips grabados localmente
│   └── pending_alerts.json          ← cola local de alertas sin enviar
├── models/
│   ├── yolo11x-pose.pt              ← modelo YOLO pretrained (no en git)
│   └── fall_lstm_final.pt           ← modelo LSTM entrenado (no en git)
│
├── domain/
│   ├── entities.py                  ← FallEvent, Alert, CameraInfo
│   ├── fall_service.py              ← FallDetectionService (lógica de ventana deslizante)
│   └── value_objects.py
│
├── application/
│   ├── ports/
│   │   ├── alert_sender.py          ← ABC AlertSender (send, is_connected, request_upload_url)
│   │   ├── clip_storage.py          ← ABC ClipStorage (upload con presigned_url externo)
│   │   ├── clip_recorder.py         ← ABC ClipRecorder
│   │   ├── fall_predictor.py        ← ABC FallPredictor
│   │   ├── keypoint_extractor.py    ← ABC KeypointExtractor
│   │   └── alert_queue.py           ← ABC AlertQueue
│   └── use_cases/
│       ├── detect_fall.py           ← DetectFall (extractor + predictor + service)
│       ├── send_alert.py            ← SendAlert (recorder + storage + sender + queue)
│       └── manage_camera.py         ← ManageCamera (scanner + selección)
│
├── infrastructure/
│   ├── detector/
│   │   ├── yolo_pose.py             ← YoloPoseExtractor (implementa KeypointExtractor)
│   │   └── lstm_model.py            ← LSTMFallPredictor (implementa FallPredictor)
│   ├── video/
│   │   ├── opencv_camera.py         ← OpenCVCamera (captura de frames)
│   │   ├── opencv_clip_recorder.py  ← OpenCVClipRecorder (buffer circular + grabación)
│   │   ├── opencv_camera_scanner.py ← escanea cámaras físicas disponibles
│   │   └── active_camera.py         ← ActiveCamera (cámara activa intercambiable)
│   ├── comms/
│   │   ├── ws_client.py             ← WebSocketClient (AlertSender + request_upload_url)
│   │   └── s3_uploader.py           ← S3ClipUploader (solo PUT a GCS, recibe presigned_url)
│   └── storage/
│       └── local_queue.py           ← LocalAlertQueue (cola persistida en JSON)
│
└── tests/
```

---

## Decisiones de diseño relevantes

**¿Por qué `request_upload_url` está en `AlertSender` y no en un puerto separado?**
`WebSocketClient` implementa ambas responsabilidades (enviar alertas y pedir URLs) sobre la misma conexión. Separarlos en dos puertos sería más puro pero requeriría inyectar dos interfaces donde hoy va una sola instancia. Se priorizó simplicidad.

**¿Por qué `S3ClipUploader` no solicita la presigned URL por HTTP?**
El endpoint REST del servidor requiere Firebase Auth Bearer token — credencial que el módulo local no posee. La presigned URL se obtiene via WebSocket (ya autenticado con `MODULE_API_KEY`) y `S3ClipUploader` solo hace el PUT.

**¿Por qué `flush_pending` corre en un thread separado (`ReconnectFlush`)?**
`_on_open` del WebSocket corre en Thread 3. `flush_pending` llama a `request_upload_url` que bloquea esperando un mensaje WebSocket — pero ese mensaje solo puede llegar si Thread 3 está libre para procesarlo. Correr `flush_pending` en Thread 3 causa deadlock; un thread separado lo evita.

**¿Por qué el `MODULE_ID` se persiste en disco?**
El módulo debe tener el mismo ID entre reinicios para que el servidor lo reconozca como el mismo dispositivo y mantenga su historial de alertas y vinculación con el usuario.

**¿Por qué buffer circular para el clip?**
El evento de caída se confirma con cierto delay (lógica de ventana). El buffer circular captura los frames previos al evento para que el clip incluya el contexto antes de la caída, no solo la caída ya ocurrida.
