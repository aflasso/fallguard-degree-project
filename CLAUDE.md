# Sistema de Detección de Caídas — Contexto del proyecto

## Qué es este sistema

Sistema distribuido para detección automática de caídas en hogares, con notificación en tiempo real al usuario a través de una aplicación móvil.

---

## Módulos del proyecto

| Módulo | Carpeta | Descripción |
|---|---|---|
| Módulo local | `fall_detection_module/` | PC en el hogar. Captura video de una cámara IP (celular en la LAN), detecta caídas con YOLO-pose + LSTM, graba clips, comunica con el servidor via WebSocket. |
| Servidor central | `fall_detection_server/` | Intermediario cloud. Gestiona módulos, reenvía alertas como push notifications (FCM), genera presigned URLs para GCS. |
| App móvil | `movile_app_module/` | Recibe alertas, visualiza clips, vincula módulo via QR, configura y previsualiza la cámara del módulo. |
| Modelo | `Modelo/` | Dataset, scripts de entrenamiento y modelo LSTM entrenado. |

Cada módulo tiene su propio `CLAUDE.md` con contexto detallado.

---

## Arquitectura general

La **fuente de video la elige el usuario desde la app** (URL de la cámara IP). El servidor la valida, la persiste en Firestore y se la empuja al módulo por WebSocket, al conectar y cada vez que cambia. `CAMERA_SOURCE` del entorno es solo un valor de arranque para pruebas.

```
[Cámara IP — celular en la LAN, MJPEG sobre HTTP o RTSP]
   ↓
[fall_detection_module — PC en el hogar]
   ├── YOLO11x-pose (pretrained) → keypoints
   ├── LSTM → 3 clases (Normal / Cayendo / Post-caída)
   ├── Buffer circular de video
   └── WebSocket client
          ↕ alertas / clips / heartbeat / estado de cámara / config
[fall_detection_server — cloud]
   ├── Firestore (módulos, usuarios, alertas)
   ├── FCM (push notifications → app móvil)
   └── GCS (presigned URLs para clips)
          ↓ push notifications / REST
[App móvil]
   └── Recibe alertas, ve clips, vincula módulo via QR
```

El servidor **nunca toca el video**: el módulo sube el clip directamente a GCS usando una presigned URL; el servidor solo almacena la URL pública resultante.

---

## Modelo de detección

| Parámetro | Valor |
|---|---|
| Extractor de keypoints | YOLO11x-pose (pretrained, sin fine-tuning) |
| Clasificador | LSTM (2 capas, hidden=128, dropout=0.3) |
| Features | 68 por frame (x,y de 17 keypoints COCO + velocidades x,y) |
| Ventana temporal | 20 frames |
| Clases | Normal (-1) / Cayendo (0) / Post-caída (1) |
| `conf_yolo` | 0.8 |
| `conf_lstm` | 0.7 (media de deque(3) para confirmar evento) |
| `min_frames` | 3 frames consecutivos para confirmar caída |

Métricas en Lecture_room + Office (dataset LE2I, no vistos en entrenamiento): Micro F1 = 0.875, Macro F1 = 0.873.

El proceso completo de entrenamiento está documentado en `Modelo/PROCESO_ENTRENAMIENTO.md`.

---

## Protocolo WebSocket (módulo ↔ servidor)

El primer mensaje del módulo **debe** ser `module_connect`. El servidor cierra con código `4000` si no.

### Módulo → Servidor

```jsonc
{ "type": "module_connect", "module_id": "uuid", "version": "1.0.0",
  "cameras": [{"id": 0, "name": "Camara integrada"}] }

{ "type": "heartbeat", "module_id": "uuid", "timestamp": "2026-04-12T14:30:00Z" }

// El heartbeat dice que el módulo vive; esto dice si además ve.
// Un módulo puede estar conectado y ciego (cámara IP congelada).
{ "type": "camera_status", "module_id": "uuid", "camera_ok": false,
  "reason": "sin frames", "timestamp": "2026-04-12T14:30:00Z" }

{ "type": "request_upload_url", "module_id": "uuid", "clip_id": "uuid-clip" }

{ "type": "fall_alert", "module_id": "uuid", "timestamp": "...",
  "confidence": 0.87, "clip_id": "uuid-clip", "clip_url": "https://..." }

{ "type": "config_ack", "module_id": "uuid", "config_version": 2 }
```

### Servidor → Módulo

```jsonc
// 'linked' indica si el módulo ya está vinculado a un usuario.
// El módulo no inicia la detección hasta estar vinculado.
{ "type": "connected", "module_id": "uuid", "linked": true }

{ "type": "module_linked" }     // vinculación en caliente → arrancar detección
{ "type": "module_unlinked" }   // desvinculación en caliente → pausar detección

// Fuente de video elegida por el usuario en la app. Se envía al conectar
// (si hay una configurada) y cada vez que el usuario la cambia.
{ "type": "set_camera_source", "url": "http://192.168.1.42:8080/video" }

{ "type": "upload_url", "clip_id": "uuid-clip",
  "presigned_url": "https://storage.googleapis.com/...", "expires_in": 300 }

{ "type": "set_camera", "camera_id": 1 }

{ "type": "config_update", "config": { "version": 3, "conf_yolo": 0.8, ... } }
```

---

## Reglas de trabajo con IA

- **Actualizar `fall_detection_server/CLAUDE.md` solo cuando se indique explícitamente.** No hacerlo de forma automática tras cada cambio de código. Cuando se pida: correr `git diff` para ver qué cambió, leer solo los archivos afectados si se necesita más contexto, y reflejar los cambios en `CLAUDE.md` de una sola vez.
