# fall_detection_module — Contexto del proyecto

## Qué es este módulo

Módulo local que corre en un PC en el hogar. Captura video desde una cámara, detecta caídas en tiempo real usando YOLO-pose + LSTM, graba clips del evento y los sube al servidor central via WebSocket.

Sus responsabilidades son:
- Capturar video desde cámara física, archivo (modo test) o **stream de red** (cámara IP/RTSP)
- **No detectar mientras el módulo no esté vinculado a un usuario** (el servidor es la fuente de verdad)
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

## Vinculación a usuario (gate de detección)

El módulo **no procesa video ni envía alertas hasta estar vinculado a un usuario**. El servidor es la fuente de verdad; el módulo nunca decide su estado por sí mismo.

- Solo se bloquea el **Thread 1 (detección)** mediante un `threading.Event` (`linked_event`). Los Threads 2 (uploader) y 3 (WebSocket) siguen activos — el Thread 3 *debe* correr para enterarse de la vinculación.
- El servidor informa el estado en el mensaje `connected` (`linked: true/false`) y lo cambia en caliente con `module_linked` / `module_unlinked`. El callback `on_link_status` en `main.py` marca/limpia `linked_event`.
- Mientras espera, el Thread 1 imprime logs informativos con el `module_id` (al entrar en espera, recordatorio cada 60 s, y al arrancar la detección).

### Persistencia del estado

El estado se persiste en `data/linked_state.txt` (`1`/`0`). Al arrancar se restaura como valor inicial del `linked_event`, de modo que un módulo ya vinculado **siga detectando tras un reinicio offline**. El estado **no se limpia al desconectarse** — solo el servidor lo cambia de forma explícita. Al reconectar, `connected` re-afirma el estado real; si te desvincularon estando offline, se corrige ahí. Cualquier clip generado en esa ventana no se sube: `GenerateUploadUrl` (servidor) exige módulo vinculado y la alerta queda en la cola local.

---

## Fuente de video

**La fuente la elige el usuario desde la app.** El servidor la valida y se la empuja al módulo por WebSocket (`set_camera_source`), al conectar y cada vez que cambia. El módulo la persiste y sobrevive reinicios offline.

### Prioridad de resolución

`config.resolve_camera_source()`:

| Orden | Fuente | Cuándo |
|---|---|---|
| 1 | Servidor (`set_camera_source`) | En vivo, al conectar y al cambiarla en la app |
| 2 | `data/camera_source.txt` | Última recibida del servidor — permite arrancar offline |
| 3 | `CAMERA_SOURCE` (env) | Solo si el módulo nunca recibió una del servidor (pruebas con dataset) |
| 4 | Sin fuente | Thread 1 espera, igual que espera la vinculación |

`CAMERA_SOURCE` tiene default **vacío**. En el momento en que el módulo recibe una fuente del servidor, la persiste, y la variable de entorno queda fuera de juego para siempre.

### Cambio de fuente en caliente: Thread 3 pide, Thread 1 abre

`ActiveCamera.request_source()` corre en Thread 3 y **solo guarda la fuente deseada**. Quien abre y cierra la cámara es Thread 1, vía `needs_open()` / `open()` al tope de su loop, cuando no hay ningún `read()` en vuelo.

Esto no es estilo: `cv2.VideoCapture` no es thread-safe. Un `release()` desde Thread 3 mientras Thread 1 está bloqueado dentro de `read()` en ese mismo objeto produce un segfault intermitente. Es el mismo motivo por el que el watchdog de cámara congelada no se implementó con un thread.

`open()` es también el camino de **reintento**: si la fuente no abre, `instance` queda en `None`, se reporta `camera_status(camera_ok=false)` y Thread 1 vuelve a intentar con backoff (1s → máx 30s). El módulo **no muere** por una cámara inaccesible.

Dentro de `open()` se revalida al final que `_desired_source` siga siendo la que se abrió: entre soltar el lock para abrir (operación lenta, con timeout) y recuperarlo, Thread 3 pudo pedir otra.

La reconexión de un stream caído se cancela si `active_cam.needs_open()` — sin eso, cambiar de cámara mientras la vieja estaba caída dejaría a Thread 1 reintentando contra la URL vieja.

### Tipos de fuente

`OpenCVCamera` distingue **archivo** de **stream de red** por el esquema de la URL (`rtsp://`, `rtmp://`, `http://`, `https://`, `udp://`, `tcp://`). Un entero es una cámara física local.

| Fuente | `read()` devuelve `None` | Comportamiento |
|---|---|---|
| Archivo / cámara física | fin del video o fallo | detiene el módulo (`stop_event`) |
| **Stream de red (cámara IP)** | corte de red **o cámara congelada** | **reconecta** con backoff exponencial (1s → máx 10s) sin matar el módulo; al reconectar aborta la grabación en curso y resetea la ventana de detección |

- En streams se aplica `CAP_PROP_BUFFERSIZE = 1` para descartar el atraso ante hipos y no acumular latencia.
- `OpenCVCamera.reconnect(should_continue)` es **cooperativo con la cancelación**: el Thread 1 pasa `lambda: not stop_event.is_set()`, así un Ctrl+C/parada interrumpe la reconexión.
- La latencia intrínseca de una cámara IP (red + codificación) es de cientos de ms y **constante**; solo crecería si la GPU no alcanzara los FPS del stream (no es el caso a 30 FPS).
- Al abrir un stream, `OpenCVCamera` construye el capture con `cv2.CAP_FFMPEG` y `open_timeout_ms` / `read_timeout_ms` (`CAMERA_OPEN_TIMEOUT_MS` / `CAMERA_READ_TIMEOUT_MS`). Archivos y webcams usan la apertura simple: esas propiedades son del backend FFmpeg.
- El fallo de apertura se captura en `main.py` (`RuntimeError` → log claro + `exit(1)`), no como traceback.

### Detección de cámara congelada

Una cámara IP puede **dejar de enviar frames sin cerrar el socket TCP**: el celular se suspende, el Wi-Fi entra en ahorro de energía. Sin timeout, `read()` bloquea para siempre — el módulo queda ciego, no devuelve `None`, nunca reconecta, y el heartbeat le sigue diciendo al servidor que está sano.

Los timeouts del backend FFmpeg instalan un *interrupt callback* que hace que `read()` retorne `False` por sí solo. Eso alimenta el camino de reconexión que ya existía. Al detectar el corte, Thread 1:

1. Loguea `ERROR` con `cam.seconds_since_last_frame()`
2. Llama a `clip_recorder.abort("corte de cámara")` — cierra el clip en curso y descarta el buffer
3. Reporta `camera_status(camera_ok=false)` al servidor
4. Reconecta con backoff; al recuperarse reporta `camera_ok=true` y hace `detect_fall.reset()`

**Docker en Windows:** la webcam USB **no** es accesible desde el contenedor (Docker corre en una VM WSL2 sin paso de dispositivos USB). Para cámara en Docker usar una **URL RTSP/HTTP** (ej. el celular como cámara IP); para webcam local, correr el módulo **nativo**.

### Nombre de la cámara reportado al servidor

`_camera_display_name()` en `main.py` anuncia `"Cámara IP"`, `"Cámara local"`, `"Video de prueba"` o `"Sin cámara"`. **Nunca incluye la URL**: ese nombre viaja al servidor y termina en la pantalla de la app.

---

## Protocolo WebSocket

### Módulo → Servidor

```jsonc
{ "type": "module_connect", "module_id": "uuid", "version": "1.0.0",
  "cameras": [{"id": 0, "name": "Camara integrada"}] }

{ "type": "heartbeat", "module_id": "uuid", "timestamp": "2026-04-12T14:30:00Z" }

// La cámara dejó de entregar frames, o volvió a entregarlos.
// Se emite en la transición y se re-afirma en cada reconexión.
{ "type": "camera_status", "module_id": "uuid", "camera_ok": false,
  "reason": "sin frames", "timestamp": "2026-04-12T14:30:00Z" }

{ "type": "request_upload_url", "module_id": "uuid", "clip_id": "uuid-clip" }

{ "type": "fall_alert", "module_id": "uuid", "timestamp": "...",
  "confidence": 0.87, "clip_id": "uuid-clip", "clip_url": "https://..." }

{ "type": "config_ack", "module_id": "uuid", "config_version": 2 }
```

`camera_status` es **edge-triggered**: se emite en la transición, no periódicamente. Pero si la cámara cae mientras el WebSocket también está caído, el evento no llega. Por eso `WebSocketClient` guarda el último estado y lo **re-afirma en `_on_open`**, justo después de `module_connect`. El servidor no reescribe si el estado no cambió.

### Servidor → Módulo

```jsonc
// Confirmación de conexión — incluye si el módulo ya está vinculado a un usuario
{ "type": "connected", "module_id": "uuid", "linked": true }

// El usuario vinculó el módulo en caliente → habilitar detección
{ "type": "module_linked" }

// El usuario desvinculó el módulo en caliente → pausar detección
{ "type": "module_unlinked" }

{ "type": "upload_url", "clip_id": "uuid-clip",
  "presigned_url": "https://storage.googleapis.com/...",
  "public_url": "https://storage.googleapis.com/...", "expires_in": 300 }

{ "type": "upload_url_error", "clip_id": "uuid-clip", "error": "descripción" }

// Fuente de video elegida por el usuario en la app. Llega al conectar
// (si hay una configurada) y cada vez que el usuario la cambia.
{ "type": "set_camera_source", "url": "http://192.168.1.42:8080/video" }

// Vestigial: selección de cámara física por índice.
{ "type": "set_camera", "camera_id": 1 }

{ "type": "config_update", "config": { "version": 3, ... } }
```

### Código vestigial

`ManageCamera`, `OpenCVCameraScanner` y el mensaje `set_camera` (índice de cámara física) quedaron sin uso desde que la fuente es siempre una URL que manda el servidor. `main.py` ya no los importa. Se conservan a la espera de decidir si se eliminan.

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
| `CAMERA_SOURCE` | `""` | **Valor de arranque únicamente.** Índice de cámara física, ruta a video o URL de stream. Vacío = esperar la fuente de la app |
| `CAMERA_SOURCE_PATH` | `data/camera_source.txt` | Dónde se persiste la última fuente enviada por el servidor |
| `CAMERA_OPEN_TIMEOUT_MS` | `5000` | Timeout de apertura del stream (solo streams de red) |
| `CAMERA_READ_TIMEOUT_MS` | `5000` | Timeout de lectura. Dispara la reconexión ante una cámara congelada. Subirlo si la red es lenta y hay falsos cortes |
| `LOCAL_QUEUE_PATH` | `data/pending_alerts.json` | Cola local persistida en disco |
| `LOG_LEVEL` | `INFO` | Nivel de logging |

El `MODULE_ID` se genera automáticamente en el primer arranque y se persiste en `data/module_id.txt`.

El estado de vinculación se persiste en `data/linked_state.txt` (configurable con `LINKED_STATE_PATH`). Es estado autogestionado por el módulo a partir de lo que reporta el servidor — no se configura manualmente.

---

## Cómo correr el módulo

### Sin Docker (desarrollo local)

```bash
cd fall_detection_module
python -m venv venv
venv\Scripts\activate          # Windows
pip install -e ".[dev]"
cp .env.template .env          # completar variables
python main.py
```

### Con Docker

```bash
cd fall_detection_module
cp docker.env.template docker.env   # completar MODULE_API_KEY y CAMERA_SOURCE
docker compose build                # primera vez o tras cambios de código
docker compose up                   # arranca module-1 (cámara real)
```

**Prerequisito:** el servidor debe estar corriendo primero (crea la red `fallguard`).

El compose define **un solo servicio activo** (`module-1`), apuntado a la cámara del celular. `module-2` y `module-3` quedan comentados: reproducen las pruebas offline con videos del dataset LE2I y requieren descomentar también sus volúmenes y el bind de `./tests/videos`.

Para ver el `module_id` generado por el contenedor (necesario para vincularlo desde la app):
```bash
docker compose logs module-1 | grep module_id
```

Para resetear la identidad de un módulo (genera nuevo UUID en el próximo arranque):
```bash
docker compose down -v
```

### Celular como cámara IP

La URL se configura **desde la app** (vincular módulo, o menú → "Cambiar cámara"). `CAMERA_SOURCE` en `docker.env` solo sirve para arrancar sin app.

App recomendada: **IP Webcam** (Android), que expone MJPEG sobre HTTP en `http://<ip>:8080/video`. Se prefiere sobre RTSP por dos motivos: cada frame es un JPEG independiente, así que tras una reconexión el primer frame ya es decodificable (con H.264 hay que esperar al siguiente keyframe); y es el único formato que la app puede previsualizar sin dependencias nativas.

El servidor **rechaza URLs con credenciales embebidas** (`rtsp://usuario:clave@host`): quedarían en texto plano en Firestore. Usar la cámara sin autenticación por ahora.

- Bajar la resolución en la app (~640×480): YOLO reescala igual y a resolución alta el MJPEG satura el Wi-Fi.
- Reservar la IP del celular en el router. Si cambia, el módulo falla al arrancar con `No se pudo abrir fuente`.
- Ajustar `VIDEO_FPS` al FPS real y mover `CONTEXT_BEFORE`/`CONTEXT_AFTER` proporcionalmente (son ~3s y ~2s).
- Con RTSP hace falta además `OPENCV_FFMPEG_CAPTURE_OPTIONS=rtsp_transport;tcp`: el RTP sobre UDP a través del NAT de WSL2 es poco confiable.

---

## Docker — detalles de implementación

### Archivos

| Archivo | Descripción |
|---|---|
| `Dockerfile` | `python:3.11-slim` + ffmpeg + dependencias via `pyproject.toml` |
| `.dockerignore` | Excluye `venv/`, `data/`, `models/`, `tests/` del build context |
| `docker-compose.yml` | `module-1` activo con GPU y red `fallguard`; `module-2` / `module-3` comentados (dataset) |
| `docker.env` / `docker.env.template` | Variables para Docker — apunta al servidor por nombre de contenedor y define `CAMERA_SOURCE` |
| `entrypoint.sh` | Convierte `.avi` → `.mp4` lossless antes de lanzar `main.py` |

### Por qué dos archivos de entorno (.env vs docker.env)

- `.env` — modo nativo (`python main.py`): `SERVER_WS_URL=ws://localhost:8000/ws`
- `docker.env` — modo Docker: `SERVER_WS_URL=ws://fall-detection-server:8000/ws`

Permiten cambiar de modo sin editar URLs manualmente.

`CAMERA_SOURCE` vive en `docker.env`, no en `docker-compose.yml`: dejó de ser un parámetro por servicio (un `.avi` distinto por contenedor) y pasó a ser uno de despliegue — la IP del celular. Los servicios de dataset comentados sí lo fijan por servicio, y eso pisa el valor de `docker.env`.

Al `entrypoint.sh` una URL `rtsp://` o `http://` le pasa de largo: su `case` solo dispara con `.avi`, `.mkv` y `.wmv`.

### Por qué el entrypoint convierte el video

`opencv-python-headless` no puede decodificar todos los codecs `.avi` (ej: DIVX del dataset LE2I). El `ffmpeg` del sistema sí puede. El entrypoint convierte a H.264 lossless (`-crf 0`) antes de arrancar, preservando calidad para que YOLO detecte correctamente.

### Identidad del módulo en Docker

Cada servicio tiene su propio volumen nombrado (`module1_data`, `module2_data`) que persiste `data/module_id.txt`. Al primer arranque se genera un UUID único por contenedor; en reinicios se reutiliza el mismo ID.

### Red Docker (fallguard)

Red bridge compartida entre el servidor y los módulos. El servidor la crea (`name: fallguard, driver: bridge`); los módulos se unen (`external: true`). Los módulos alcanzan al servidor por nombre de contenedor: `fall-detection-server:8000`.

### GPU (Blackwell / RTX 50xx)

La RTX 5060 (sm_120) requiere PyTorch nightly con CUDA 12.x — los wheels estables solo soportan hasta sm_90. El Dockerfile instala `--pre torch torchvision --index-url .../nightly/cu130`. Cada servicio reserva la GPU via `deploy.resources.reservations.devices`.

---

## Estructura de archivos

```
fall_detection_module/
├── main.py                          ← orquesta los 3 threads, wiring de dependencias
├── config.py                        ← variables de entorno, MODULE_ID persistido
├── pyproject.toml
├── .env / .env.template             ← configuración para modo nativo
├── Dockerfile                       ← imagen Docker del módulo
├── .dockerignore
├── docker-compose.yml               ← module-1 (cámara real) con GPU y red fallguard; dataset comentado
├── docker.env / docker.env.template ← configuración para modo Docker
├── entrypoint.sh                    ← conversión de video .avi → .mp4 antes de main.py
├── data/
│   ├── module_id.txt                ← UUID del módulo (generado en primer arranque)
│   ├── linked_state.txt             ← estado de vinculación persistido (1/0)
│   ├── camera_source.txt            ← última fuente enviada por el servidor
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
│   │   ├── camera.py                ← ABC Camera (read, is_stream, seconds_since_last_frame, reconnect)
│   │   ├── alert_sender.py          ← ABC AlertSender (send, is_connected, request_upload_url)
│   │   ├── clip_storage.py          ← ABC ClipStorage (upload con presigned_url externo)
│   │   ├── clip_recorder.py         ← ABC ClipRecorder (add_frame, record, is_recording, abort)
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
│   │   ├── opencv_camera.py         ← OpenCVCamera (stream vs archivo, timeouts FFmpeg, reconexión)
│   │   ├── opencv_clip_recorder.py  ← OpenCVClipRecorder (buffer circular + grabación + abort)
│   │   ├── opencv_camera_scanner.py ← (vestigial) escanea cámaras físicas
│   │   └── active_camera.py         ← ActiveCamera (fuente en caliente: Thread 3 pide, Thread 1 abre)
│   ├── comms/
│   │   ├── ws_client.py             ← WebSocketClient (AlertSender + request_upload_url + camera_status)
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

**¿Por qué instalar dependencias desde `pyproject.toml` en Docker y no listarlas manualmente?**
Listar paquetes manualmente en el Dockerfile puede resolver versiones distintas a las del entorno local, causando diferencias en keypoints de YOLO/LSTM que rompen la detección. `pip install -e .` garantiza la misma combinación de versiones que funciona fuera de Docker. PyTorch CUDA se pre-instala antes para que pip lo vea como ya satisfecho.

**¿Por qué solo se bloquea el Thread 1 con `linked_event` y no todos los threads?**
El Thread 3 (WebSocket) debe seguir corriendo para recibir el mensaje que indica que el módulo fue vinculado — bloquearlo causaría un deadlock (nunca se enteraría). El Thread 2 (uploader) corre ocioso porque sin detección no llegan clips. Solo la detección (cara, con YOLO+LSTM) se pausa.

**¿Por qué un stream se reconecta y un archivo no?**
Para un archivo, `read()` que devuelve `None` es el fin del video → detener es correcto. Para una cámara IP, `None` suele ser un corte temporal de red; matar el módulo por un microcorte de Wi-Fi sería frágil. Por eso `OpenCVCamera` distingue la fuente y, en streams, reintenta reconectar en vez de terminar.

**¿Por qué timeouts de FFmpeg y no un thread watchdog que vigile el último frame?**
La implementación obvia sería un thread que, si `last_frame_ts` está viejo, llame a `cap.release()` para desbloquear a Thread 1. Pero `cv2.VideoCapture` **no es thread-safe**: liberar el capture mientras otro thread está bloqueado dentro de `read()` puede causar un segfault intermitente. `CAP_PROP_READ_TIMEOUT_MSEC` instala un interrupt callback dentro del backend FFmpeg, que hace que `read()` retorne solo, en la capa que corresponde y sin que nadie toque el capture desde afuera. El problema nunca fue "falta un watchdog", fue "`read()` no tiene timeout".

**¿Por qué `abort()` entrega el clip parcial en vez de descartarlo?**
Si la cámara se corta en medio de una grabación, los `context_after` frames nunca llegan, `_finish_recording()` nunca corre y el grabador queda trabado en `is_recording()` — toda caída posterior se descarta con "Ya hay una grabación en curso". `abort()` cierra el `VideoWriter` e invoca `on_ready`, así que el clip sale corto pero la alerta se envía. La caída ya fue confirmada por el modelo: descartarla convertiría un bug de "deja de alertar para siempre" en otro de "se come justo la alerta de la caída durante la cual se cortó la cámara". El buffer circular se limpia siempre, porque sus frames son anteriores al corte y empalmarlos con los de después daría un clip con un salto temporal invisible.

**¿Por qué Thread 3 no abre la cámara al recibir `set_camera_source`?**
`cv2.VideoCapture` no es thread-safe. Thread 1 puede estar bloqueado dentro de `read()` sobre la cámara vieja; liberarla desde otro thread es un segfault intermitente. Por eso el cambio es en dos tiempos: Thread 3 guarda la fuente deseada, Thread 1 la abre al tope de su loop. Es el mismo razonamiento que descartó el watchdog con thread.

**¿Por qué el módulo ya no hace `exit(1)` si la cámara no abre?**
Antes la fuente venía del entorno y un fallo de apertura era un error de configuración: morir era correcto. Ahora la fuente la manda el usuario desde la app y puede estar mal, o la cámara puede estar apagada en ese momento. Matar el módulo lo dejaría sin WebSocket, y entonces el usuario **no podría corregir la URL** — el mensaje para arreglarlo llega justamente por ahí. El módulo espera, reporta `camera_ok=false` y reintenta.

**¿Por qué la fuente persistida le gana a `CAMERA_SOURCE`?**
La persistida es lo último que el usuario eligió en la app. El env es un valor de arranque para pruebas. Si el env ganara, un `docker compose up` con un `.avi` viejo sobrescribiría en silencio la cámara real del hogar.

**¿Por qué el estado de cámara se re-afirma en cada reconexión?**
`camera_status` se emite en la transición. Si la cámara cae mientras el WebSocket también está caído, el evento no llega a ningún lado. `WebSocketClient` guarda el último estado y lo reenvía en `_on_open`, así un servidor reiniciado o un módulo que estuvo offline convergen al estado real. El costo es que la mayoría de los `camera_status` no son transiciones — por eso el servidor no reescribe Firestore si el valor no cambió.

**¿Por qué el estado de vinculación no se limpia al desconectarse?**
Un módulo ya vinculado que pierde conexión debe seguir detectando y encolar alertas offline. Si se limpiara al desconectar, una caída de red apagaría la detección. El estado solo cambia cuando el servidor lo dice explícitamente (`connected` / `module_linked` / `module_unlinked`), y se persiste en disco para sobrevivir reinicios offline.

**¿Por qué `restart: no` en los módulos Docker?**
En modo test el video termina y el módulo sale limpiamente (exit 0). Con `restart: always` se reiniciaría en bucle automáticamente; con `restart: no` el operador controla cuándo volver a correr.
