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
| Autenticación REST | Firebase Auth (Bearer token verificado por endpoint) |
| Autenticación WebSocket | API key via query param `?api_key=` |
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
| `AlertStatus` | `DETECTED`, `CONFIRMED`, `FALSE_ALARM` | Estado de la alerta. `DETECTED` es el estado inicial; el usuario puede confirmar o descartar. |

---

## Casos de uso

**`application/use_cases/`**

| Caso de uso | Disparado por | Qué hace |
|---|---|---|
| `ConnectModule` | WebSocket `module_connect` | Registra el módulo en Firestore si es nuevo, actualiza status a CONNECTED |
| `DisconnectModule` | WebSocket disconnect | Marca el módulo como DISCONNECTED en Firestore |
| `HandleFallAlert` | WebSocket `fall_alert` | Guarda la Alert en Firestore y envía push FCM al usuario vinculado |
| `GenerateUploadUrl` | WebSocket `request_upload_url` | Genera presigned URL GCS para PUT del clip. Requiere módulo vinculado a usuario. |
| `LinkModule` | REST `POST /api/modules/link` | Asocia un `module_id` a un `user_id`. Rechaza si el módulo ya está vinculado a otro usuario. |

---

## API WebSocket

**Endpoint:** `ws://<host>/ws?api_key=<MODULE_API_KEY>`

La conexión requiere el query param `api_key`. Si falta o es incorrecto, el servidor cierra con código `4001`. El primer mensaje tras conectar **debe** ser `module_connect`; si no, cierra con código `4000`.

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

// Respuesta a request_upload_url (éxito)
{ "type": "upload_url", "clip_id": "uuid-clip",
  "presigned_url": "https://storage.googleapis.com/...",
  "public_url": "https://storage.googleapis.com/...",
  "expires_in": 300 }

// Respuesta a request_upload_url (error — módulo no vinculado, etc.)
{ "type": "upload_url_error", "clip_id": "uuid-clip", "error": "descripción" }
```

---

## API REST

**Base path:** `/api`
**Autenticación:** todos los endpoints requieren `Authorization: Bearer <firebase-id-token>`.
El token se verifica con Firebase Auth. El `uid` del token debe coincidir con el `user_id` del recurso (verificado por `require_same_user`).

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/users` | Crea un usuario nuevo. Retorna `409` si ya existe. |
| `PATCH` | `/api/users/{user_id}/fcm-token` | Actualiza el FCM token del usuario |
| `POST` | `/api/modules/link` | Vincula módulo a usuario. Retorna `403` si ya está vinculado a otro usuario. |
| `GET` | `/api/modules/status/{module_id}` | Estado del módulo: `status`, `last_seen`, `cameras` |
| `GET` | `/api/alerts?user_id={uid}[&status=detected\|confirmed\|falseAlarm]` | Historial de alertas del usuario (desc por timestamp). Filtro de estado opcional. |
| `PATCH` | `/api/alerts/{alert_id}/seen` | Actualiza el status de una alerta. Solo acepta `confirmed` o `falseAlarm`. |
| `DELETE` | `/api/alerts/{alert_id}` | Elimina una alerta del historial. Verifica que pertenezca al usuario del token. |
| `DELETE` | `/api/alerts?user_id={uid}` | Elimina todas las alertas del usuario. |
| `GET` | `/api/clips/read-url?alert_id={id}` | Genera presigned URL de lectura GCS (15 min) para el clip de una alerta. |
| `POST` | `/api/clips/upload-url` | Genera presigned URL para subir un clip — **solo para la app móvil**, no para el módulo local. |
| `POST` | `/api/auth/change-password` | Cambia la contraseña de una cuenta `password` (no Google). Requiere token en header. |
| `POST` | `/api/auth/reset-password` | Genera link de restablecimiento de contraseña y lo retorna. Sin autenticación requerida. |

> El módulo local solicita presigned URLs via WebSocket (`request_upload_url`), no via REST.

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

- **`send_fall_alert`** — incluye campo `notification` (título + body) para que Android muestre la notificación del sistema en background, más `data` con `alert_id`, `timestamp`, `clip_url`. Prioridad `high` / `max` para heads-up display.
- **`send_module_disconnected`** — notifica cuando el módulo deja de enviar heartbeats.

### GCS (Google Cloud Storage)

`infrastructure/gcs/presigned_url.py` genera dos tipos de presigned URLs v4:

- **`generate_upload_url`** — PUT, expiración 5 min. Usada por el módulo local via WebSocket para subir clips.
- **`generate_read_url`** — GET, expiración 15 min. Usada por la app móvil via `GET /api/clips/read-url` para reproducir clips. Se genera bajo demanda al abrir la pantalla de revisión, no al crear la alerta.

Path del objeto en el bucket: `clips/{user_id}/{module_id}/{clip_id}.mp4`

El módulo local hace el PUT directamente a GCS — el servidor solo recibe la `public_url` resultante en el mensaje `fall_alert`. Los clips subidos via presigned URL **no tienen Firebase download token**, por lo que `firebase_storage.getDownloadURL()` no funciona — siempre usar `generate_read_url`.

### Reglas de Firebase Storage recomendadas

```js
rules_version = '2';
service firebase.storage {
  match /b/{bucket}/o {
    match /clips/{userId}/{moduleId}/{clipId} {
      allow read: if request.auth != null && request.auth.uid == userId;
      allow write: if false;  // solo via presigned URL
    }
    match /{allPaths=**} {
      allow read, write: if false;
    }
  }
}
```

### Reglas de Firestore recomendadas

```js
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /users/{userId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }
    match /modules/{moduleId} {
      allow read: if request.auth != null && resource.data.user_id == request.auth.uid;
      allow write: if false;
    }
    match /alerts/{alertId} {
      allow read: if request.auth != null && resource.data.user_id == request.auth.uid;
      allow update: if request.auth != null
                    && resource.data.user_id == request.auth.uid
                    && request.resource.data.diff(resource.data)
                         .affectedKeys().hasOnly(['seen', 'status']);
      allow create, delete: if false;
    }
    match /{document=**} {
      allow read, write: if false;
    }
  }
}
```

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
| `MODULE_API_KEY` | `""` | API key que deben presentar los módulos al conectarse via WebSocket |

Generar `MODULE_API_KEY`: `python -c "import secrets; print(secrets.token_hex(32))"`

El archivo `credentials/serviceAccountKey.json` se obtiene desde Firebase Console → Project Settings → Service accounts → Generate new private key. Está en `.gitignore`.

---

## Cómo correr el servidor

### Sin Docker (desarrollo local)

```bash
cd fall_detection_server
python -m venv venv
venv\Scripts\activate          # Windows
pip install -e ".[dev]"
cp .env.template .env          # completar variables
python main.py
```

### Con Docker

```bash
cd fall_detection_server
docker compose build            # primera vez o tras cambios de código
docker compose up -d            # arranca en background y crea la red fallguard
docker compose logs -f          # ver logs
```

**El servidor debe arrancar antes que los módulos** — su compose crea la red Docker `fallguard` que los módulos necesitan para conectarse.

---

## Docker — detalles de implementación

### Archivos

| Archivo | Descripción |
|---|---|
| `Dockerfile` | `python:3.11-slim` + dependencias via `pyproject.toml`, sin reload |
| `.dockerignore` | Excluye `venv/`, `.env`, `credentials/`, `tests/` del build context |
| `docker-compose.yml` | Servicio `fall-detection-server`, puerto 8000, red `fallguard`, credentials montadas |

### Red Docker (fallguard)

El compose del servidor define la red con `name: fallguard` y `driver: bridge` — Docker la crea con ese nombre exacto al hacer `docker compose up`. Los módulos se unen a ella con `external: true`. Sin el prefijo `name:`, Docker la crearía como `fall_detection_server_fallguard` y los módulos no la encontrarían.

### Credenciales Firebase

`credentials/serviceAccountKey.json` se monta como volumen read-only (`./credentials:/app/credentials:ro`) — nunca se hornea en la imagen. Esto permite usar la misma imagen en distintos entornos con distintas credenciales.

### CMD vs python main.py

El Dockerfile usa `CMD ["uvicorn", "main:app", ...]` directamente en lugar de `python main.py` para evitar el `reload=True` que tiene el entry point local. En un contenedor el file watching no tiene sentido y genera overhead innecesario.

---

## Estructura de archivos

```
fall_detection_server/
├── main.py                          ← startup, wiring de dependencias, endpoint WebSocket
├── config.py                        ← variables de entorno con defaults
├── pyproject.toml                   ← dependencias y configuración del paquete
├── .env / .env.template
├── Dockerfile                       ← imagen Docker del servidor
├── .dockerignore
├── docker-compose.yml               ← servicio + red fallguard
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
│   │   ├── notification_sender.py   ← ABC NotificationSender
│   │   └── upload_url_generator.py  ← ABC UploadUrlGenerator(clip_id, user_id, module_id)
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
│   ├── rest.py                      ← RestHandler + APIRouter (sin dependencies globales)
│   ├── websocket.py                 ← WebSocketHandler
│   └── schemas/
│       ├── module_schemas.py
│       ├── alert_schemas.py
│       ├── user_schemas.py
│       ├── auth_schemas.py          ← ChangePasswordSchema, ResetPasswordSchema
│       └── __init__.py
│
└── tests/
```

---

## Decisiones de diseño relevantes

**¿Por qué el servidor no almacena los clips?**
El módulo sube el clip directamente a GCS usando una presigned URL. El servidor solo almacena la URL pública. Esto evita que el servidor sea un cuello de botella para archivos de video.

**¿Por qué el módulo usa WebSocket para pedir la presigned URL en lugar del REST API?**
El endpoint REST `/api/clips/upload-url` requiere Firebase Auth Bearer token — credencial que el módulo local (PC) no posee. El WebSocket ya está autenticado via `MODULE_API_KEY`, así que la presigned URL se solicita por ahí.

**¿Por qué API key para WebSocket y no Firebase Auth?**
El módulo local es un proceso de PC, no un usuario de Firebase. No puede obtener un Firebase ID token. Un API key compartido es el mecanismo más simple y efectivo para autenticar un cliente de servidor a servidor.

**¿Por qué `LinkModule` rechaza si el módulo ya tiene dueño?**
Evita que un usuario robe el módulo de otro escaneando su QR. Un módulo solo puede reasignarse si primero se desvincula explícitamente.

**¿Por qué `POST /api/users` retorna 409 en lugar de upsert silencioso?**
Hace explícito el contrato: este endpoint es para creación, no actualización. El update de datos de usuario va por `PATCH /api/users/{user_id}/fcm-token`.

**¿Por qué los repositorios de dominio son ABCs y no directamente Firestore?**
Permite testear casos de uso con repositorios en memoria sin tocar Firebase.

**¿Por qué `require_same_user` en cada endpoint REST?**
Un usuario autenticado en Firebase solo puede leer y modificar sus propios recursos.

**¿Por qué la presigned URL de lectura se genera bajo demanda y no al crear la alerta?**
Las URLs tienen 15 min de vigencia. Si se generaran al momento de la alerta, expirarían antes de que el usuario abra la app. Al generarlas cuando el usuario abre la pantalla de revisión, los 15 min empiezan desde ese momento.

**¿Por qué `AlertStatus` usa `DETECTED` y no `PENDING`?**
Documentos antiguos en Firestore usaban `"pending"` — el repositorio normaliza ese valor a `"detected"` via `_normalize_status()` para mantener compatibilidad hacia atrás sin migración de datos.
