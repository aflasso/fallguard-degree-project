# fall_detection_server — Contexto del proyecto

## Qué es este módulo

Servidor central del sistema de detección de caídas. Actúa como intermediario entre los módulos locales de detección (PCs en el hogar) y la aplicación móvil del usuario.

Sus responsabilidades son:
- Mantener el estado de conexión de los módulos locales via WebSocket
- Recibir alertas de caída y reenviarlas al usuario como push notifications (FCM)
- Gestionar la vinculación módulo ↔ usuario
- Generar presigned URLs para que los módulos suban clips de video directamente a GCS
- Exponer una API REST para la app móvil (historial de alertas, estado del módulo, gestión de usuario)

Este servidor **nunca toca el video**: solo genera la URL de subida y almacena la URL pública resultante.

---

## Lugar en el sistema

```
[Módulo local (PC en el hogar)]
   └── WebSocket ──────────────────────────────────┐
                                                   ▼
                                        [fall_detection_server]  ← este módulo
                                           ├── Firestore (estado, alertas, usuarios)
                                           ├── FCM (push notifications)
                                           └── GCS (presigned URLs para clips)
                                                   │
                              ┌────────────────────┘
                              ▼
                        [App móvil]
                           └── HTTP REST ──► /api/*
```

---

## Stack tecnológico

| Componente | Tecnología |
|---|---|
| Framework | FastAPI (async) |
| WebSocket | FastAPI WebSocket nativo |
| Base de datos | Firestore (firebase-admin, async) |
| Push notifications | Firebase Cloud Messaging (FCM) |
| Almacenamiento de clips | Google Cloud Storage (presigned URL v4) |
| Autenticación | Firebase Auth (Bearer token verificado por endpoint) |
| Runtime | Python 3.11+ / uvicorn |

---

## Arquitectura interna

El servidor sigue **Clean Architecture** con cuatro capas. La regla de dependencia es estricta: las capas internas no conocen las externas.

```
api/          ← HTTP y WebSocket. Valida entradas (Pydantic), delega a casos de uso.
application/  ← Casos de uso y puertos (interfaces). Lógica de negocio pura.
domain/       ← Entidades y contratos de repositorios. Sin dependencias externas.
infrastructure/ ← Implementaciones concretas: Firestore, FCM, GCS, WebSocket manager.
```

### Inyección de dependencias

Toda la cableada ocurre en `main.py` → `startup()`. No hay service locator ni singletons globales. Las instancias se pasan por constructor a `WebSocketHandler` y `RestHandler`.

---

## Entidades de dominio

**`domain/entities.py`**

| Entidad | Campos clave | Descripción |
|---|---|---|
| `Module` | `module_id`, `status`, `last_seen`, `user_id`, `cameras` | Módulo local de detección. `user_id` es `None` si no está vinculado. |
| `User` | `user_id`, `email`, `fcm_token` | Usuario de la app móvil. `fcm_token` es necesario para recibir push. |
| `Alert` | `alert_id`, `module_id`, `user_id`, `timestamp`, `confidence`, `clip_url`, `seen`, `status` | Evento de caída confirmado. |
| `ModuleStatus` | `CONNECTED`, `DISCONNECTED` | Estado de conexión del módulo. |
| `AlertStatus` | `PENDING`, `CONFIRMED`, `FALSE_ALARM` | Estado que el usuario puede actualizar desde la app. |

---

## Casos de uso

**`application/use_cases/`**

| Caso de uso | Disparado por | Qué hace |
|---|---|---|
| `ConnectModule` | WebSocket `module_connect` | Registra el módulo en Firestore si es nuevo, actualiza status a CONNECTED |
| `DisconnectModule` | WebSocket disconnect | Marca el módulo como DISCONNECTED en Firestore |
| `HandleFallAlert` | WebSocket `fall_alert` | Guarda la Alert en Firestore y envía push FCM al usuario vinculado |
| `GenerateUploadUrl` | WebSocket `request_upload_url` o REST | Genera presigned URL GCS para PUT del clip |
| `LinkModule` | REST `POST /api/modules/link` | Asocia un `module_id` a un `user_id` en Firestore |

---

## API WebSocket

**Endpoint:** `ws://<host>/ws`

El primer mensaje que envía el módulo **debe** ser `module_connect`. Si no, el servidor cierra con código `4000`.

### Mensajes módulo → servidor

```jsonc
// Conexión inicial (obligatorio como primer mensaje)
{ "type": "module_connect", "module_id": "uuid", "version": "1.0.0",
  "cameras": [{"id": 0, "name": "Camara integrada"}] }

// Heartbeat (cada 30 s)
{ "type": "heartbeat", "module_id": "uuid", "timestamp": "2026-04-12T14:30:00Z" }

// Solicitar URL para subir clip
{ "type": "request_upload_url", "module_id": "uuid", "clip_id": "uuid-clip" }

// Enviar alerta de caída (después de subir el clip)
{ "type": "fall_alert", "module_id": "uuid", "timestamp": "...",
  "confidence": 0.87, "clip_id": "uuid-clip", "clip_url": "https://..." }

// Confirmar recepción de configuración
{ "type": "config_ack", "module_id": "uuid", "config_version": 2 }
```

### Mensajes servidor → módulo

```jsonc
// Confirmación de conexión
{ "type": "connected", "module_id": "uuid" }

// Respuesta a request_upload_url
{ "type": "upload_url", "clip_id": "uuid-clip",
  "presigned_url": "https://storage.googleapis.com/...",
  "public_url": "https://storage.googleapis.com/...",
  "expires_in": 300 }
```

---

## API REST

**Base path:** `/api`  
**Autenticación:** todos los endpoints requieren `Authorization: Bearer <firebase-id-token>`.  
El token se verifica con Firebase Auth. El `uid` del token debe coincidir con el `user_id` del recurso (verificado por `require_same_user`), excepto en endpoints de solo lectura de módulos.

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/users` | Crea un usuario nuevo (llamado en el primer login de la app) |
| `PATCH` | `/api/users/{user_id}/fcm-token` | Actualiza el FCM token del usuario |
| `POST` | `/api/modules/link` | Vincula módulo a usuario (body: `{module_id, user_id}`) |
| `GET` | `/api/modules/status/{module_id}` | Estado del módulo: `status`, `last_seen`, `cameras` |
| `GET` | `/api/alerts?user_id={uid}` | Historial de alertas del usuario (desc por timestamp) |
| `PATCH` | `/api/alerts/{alert_id}/seen` | Marca alerta como vista y actualiza su status |
| `POST` | `/api/clips/upload-url` | Genera presigned URL para subir un clip (body: `{module_id, clip_id}`) |

---

## Infraestructura

### Firestore

Colecciones:

| Colección | Documento | Descripción |
|---|---|---|
| `modules` | `{module_id}` | Estado y metadatos del módulo |
| `users` | `{user_id}` | Perfil del usuario con FCM token |
| `alerts` | `{alert_id}` | Alertas de caída con URL de clip |

Los repositorios implementan una clase base genérica `FirestoreRepository[T]` en `infrastructure/firestore/base_repository.py` que provee `save`, `find_by_id`, `find_all`, `delete`. Cada repositorio concreto implementa `_to_dict`, `_from_dict` y `_get_id`.

### FCM (Firebase Cloud Messaging)

`infrastructure/firebase/fcm_sender.py` implementa el puerto `NotificationSender`. Envía dos tipos de push:

- **`send_fall_alert`** — título "Caída detectada", incluye `alert_id`, `timestamp`, `clip_url` en el payload `data`.
- **`send_module_disconnected`** — notifica cuando el módulo deja de enviar heartbeats.

### GCS (Google Cloud Storage)

`infrastructure/gcs/presigned_url.py` genera presigned URLs v4 para PUT con expiración de 5 minutos. El módulo local hace el PUT directamente a GCS — el servidor solo recibe la `public_url` resultante en el mensaje `fall_alert`.

### WebSocket Connection Manager

`infrastructure/websocket/connection_manager.py` mantiene un dict `{module_id: WebSocket}` en memoria. Es el único estado en memoria del servidor (el resto vive en Firestore). Si el servidor se reinicia, los módulos necesitan reconectar.

---

## Configuración

Variables de entorno (ver `.env.template`):

| Variable | Default | Descripción |
|---|---|---|
| `FIREBASE_CREDENTIALS_PATH` | `credentials/serviceAccountKey.json` | Ruta al serviceAccountKey.json de Firebase |
| `GCS_BUCKET_NAME` | `fall-detection-clips` | Bucket de Firebase Storage (sin `gs://`) |
| `HOST` | `0.0.0.0` | Host del servidor |
| `PORT` | `8000` | Puerto del servidor |
| `LOG_LEVEL` | `INFO` | Nivel de logging |
| `HEARTBEAT_TIMEOUT` | `90` | Segundos sin heartbeat para considerar módulo desconectado |

El archivo `credentials/serviceAccountKey.json` se obtiene desde Firebase Console → Project Settings → Service accounts → Generate new private key. Está en `.gitignore`.

---

## Cómo correr el servidor

```bash
cd fall_detection_server
python -m venv venv
venv\Scripts\activate          # Windows
pip install -e ".[dev]"
cp .env.template .env          # completar variables
python main.py
# o en producción:
uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## Estructura de archivos

```
fall_detection_server/
├── main.py                          ← startup, wiring de dependencias, endpoints raíz
├── config.py                        ← variables de entorno con defaults
├── pyproject.toml                   ← dependencias y configuración del paquete
├── .env / .env.template
├── credentials/
│   └── serviceAccountKey.json       ← ignorado por git, credenciales Firebase
│
├── domain/
│   ├── entities.py                  ← Module, User, Alert, ModuleStatus, AlertStatus
│   └── repositories/
│       ├── base_repository.py       ← ABC genérico Repository[T]
│       ├── module_repository.py     ← ABC ModuleRepository
│       ├── alert_repository.py      ← ABC AlertRepository
│       └── user_repository.py       ← ABC UserRepository
│
├── application/
│   ├── dtos/
│   │   ├── module_dtos.py           ← ConnectModuleCommand, LinkModuleCommand, CameraInfoDTO
│   │   ├── alert_dtos.py            ← ProcessFallAlertCommand, GenerateUploadUrlCommand
│   │   └── user_dtos.py             ← CreateUserCommand, UpdateFCMTokenCommand
│   ├── ports/
│   │   ├── connection_manager.py    ← ABC ConnectionManager (send, is_connected)
│   │   ├── notification_sender.py   ← ABC NotificationSender (send_fall_alert, send_module_disconnected)
│   │   └── upload_url_generator.py  ← ABC UploadUrlGenerator + UploadUrlResult
│   └── use_cases/
│       ├── connect_module.py
│       ├── disconnect_module.py
│       ├── handle_fall_alert.py
│       ├── generate_upload_url.py
│       └── link_module.py
│
├── infrastructure/
│   ├── firestore/
│   │   ├── base_repository.py       ← FirestoreRepository[T] con CRUD genérico async
│   │   ├── module_repository.py     ← FirestoreModuleRepository
│   │   ├── alert_repository.py      ← FirestoreAlertRepository
│   │   └── user_repository.py       ← FirestoreUserRepository
│   ├── firebase/
│   │   └── fcm_sender.py            ← FCMNotificationSender
│   ├── gcs/
│   │   └── presigned_url.py         ← GCSPresignedUrlGenerator (presigned URL v4)
│   └── websocket/
│       └── connection_manager.py    ← WebSocketConnectionManager (dict en memoria)
│
├── api/
│   ├── auth.py                      ← verify_token (Firebase Auth), require_same_user
│   ├── rest.py                      ← RestHandler + router APIRouter
│   ├── websocket.py                 ← WebSocketHandler
│   └── schemas/
│       ├── module_schemas.py        ← ModuleConnectSchema, HeartbeatSchema, ModuleStatusSchema, ...
│       ├── alert_schemas.py         ← FallAlertSchema, RequestUploadUrlSchema, AlertResponseSchema, ...
│       ├── user_schemas.py          ← CreateUserSchema, UpdateFCMTokenSchema
│       └── __init__.py              ← re-exporta todos los schemas
│
└── tests/                           ← carpeta existente, tests pendientes de implementar
```

---

## Decisiones de diseño relevantes

**¿Por qué el servidor no almacena los clips?**
El módulo sube el clip directamente a GCS usando una presigned URL. El servidor solo almacena la URL pública. Esto evita que el servidor sea un cuello de botella para archivos de video y simplifica la escalabilidad.

**¿Por qué el `WebSocketConnectionManager` vive en memoria y no en Firestore?**
Las conexiones WebSocket son estado efímero — no tiene sentido persistirlas. Firestore almacena el estado durable (si el módulo está CONNECTED o DISCONNECTED), pero la referencia al objeto `WebSocket` activo solo puede vivir en el proceso que la acepta.

**¿Por qué `module_connect` es el primer mensaje obligatorio y no parte del handshake HTTP?**
Permite que el módulo se identifique con su UUID propio (no derivado de la autenticación HTTP) y envíe la lista de cámaras disponibles en el mismo mensaje. Simplifica el protocolo al tenerlo todo en un solo flujo WebSocket.

**¿Por qué los repositorios de dominio son ABCs y no directamente Firestore?**
Permite testear casos de uso con repositorios en memoria sin tocar Firebase. La capa de aplicación no sabe qué base de datos usa.

**¿Por qué `require_same_user` en cada endpoint REST?**
Un usuario autenticado en Firebase solo puede leer y modificar sus propios recursos. El `uid` del token JWT de Firebase se compara con el `user_id` del recurso antes de ejecutar cualquier operación.
