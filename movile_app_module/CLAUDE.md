# movile_app_module — Contexto del proyecto

## Qué es este módulo

Aplicación móvil (Flutter) del sistema de detección de caídas. Es la interfaz del usuario final: recibe alertas en tiempo real, permite revisar el clip de cada caída, gestiona los módulos vinculados y la cuenta.

Sus responsabilidades son:
- Autenticar al usuario (email/contraseña o Google) con Firebase Auth
- Recibir push notifications de caída (FCM) y abrir la pantalla de la alerta
- Mostrar el estado del hogar en tiempo real (alertas pendientes, módulos conectados/desconectados)
- Vincular / desvincular módulos y asignarles un nombre visible
- Reproducir el clip de una alerta (presigned URL) y confirmarla / descartarla
- Gestionar perfil, seguridad (cambio/reset de contraseña) y ajustes

---

## Lugar en el sistema

```
[fall_detection_server]
   ├── FCM ──push──► app (alerta de caída)
   ├── Firestore ──snapshots()──► app (lectura en vivo: alertas, módulos)
   ├── REST /api/* ◄── app (escrituras: link/unlink, confirmar alerta, perfil)
   └── GCS (presigned read URL) ──► app reproduce el clip
[App móvil]  ← este módulo
```

El servidor **nunca** sirve el video: la app pide una presigned URL de lectura (`GET /api/clips/read-url`) y reproduce directo desde GCS.

---

## Stack tecnológico

| Componente | Tecnología |
|---|---|
| Framework | Flutter (Material 3) |
| Autenticación | Firebase Auth (email/password + Google OAuth) |
| Lectura de datos | Cloud Firestore (listeners `snapshots()` en vivo) |
| Escritura de datos | REST al servidor (`http`) |
| Push notifications | Firebase Cloud Messaging + `flutter_local_notifications` (Android) |
| Reproducción de clip | `video_player` (móvil) / enlace externo (web) |
| Tipografía / UI | `google_fonts` (Manrope), tema en `theme/app_theme.dart` |

---

## Arquitectura

```
lib/
├── main.dart            ← arranque, MaterialApp, rutas, gate de sesión
├── navigation_key.dart  ← navigatorKey global (navegar desde handlers FCM)
├── firebase_options.dart
├── models/              ← modelos de datos (AlertModel, AlertStatus)
├── services/            ← lógica de datos y side-effects (Auth, Alert, FCM, ApiClient)
├── screens/             ← pantallas
├── widgets/             ← compartidos (FallGuardAppBar, MjpegView, camera_check)
└── theme/               ← AppTheme (colores, estilos)
```

No hay gestor de estado externo (Provider/Bloc): las pantallas usan `StreamBuilder` sobre los streams de los servicios. Los servicios son clases con métodos `static`.

### Lectura en tiempo real vs escritura

- **Lecturas en vivo** (alertas, módulos, perfil): directo de Firestore con `snapshots()`. El dashboard y el historial reaccionan al instante. La autorización la hacen las reglas de Firestore (cada usuario solo ve sus documentos).
- **Escrituras** (vincular/desvincular, confirmar/descartar/borrar alerta, perfil, FCM token, contraseña): por **REST** al servidor.

---

## Servicios

| Servicio | Responsabilidad |
|---|---|
| `AuthService` | Login email/Google, registro (atómico: si falla el perfil borra el user de Auth), `updateDisplayName`, cambio/reset de contraseña (reautentica en cliente y delega al servidor) |
| `AlertService` | Streams en vivo (`alertsStream`, `linkedModulesStream`, `userProfileStream`), helper `isCameraDown` + escrituras REST (`linkModule`, `unlinkModule`, `renameModule`, `setModuleCamera`, `updateAlertStatus`, `deleteAlert`, `getClipReadUrl`, `createUserProfile`, `updateFcmToken`) |
| `FcmService` | Registra el token FCM, escucha mensajes (foreground/background/cold start) y navega a `/emergency` ante `type == 'fall_detected'` usando `navigatorKey` |
| `ApiClient` | Helper REST (base URL, headers con Bearer, `postJson`, `extractError`). Usado por `AuthService` |

> Nota: `AlertService` define su propio `_baseUrl`/`_headers` (equivalentes a `ApiClient`). Conviven por evolución del código.

---

## Estado del dashboard (pantalla principal)

El header (etiqueta + nombre + avatar con badge) y la tarjeta de estado son **dinámicos**, combinando dos streams en vivo (`alertsStream` + `linkedModulesStream`). Prioridad de estados:

| Prioridad | Condición | Header | Tarjeta de estado |
|---|---|---|---|
| 1 | Hay alertas sin confirmar (`status == detected`) | "N alerta(s) sin confirmar", rojo | Preview de hasta 3 alertas (tap → `/emergency`) |
| 2 | No hay módulos vinculados | "Sin módulos vinculados", gris | Invitación + botón "Vincular módulo" |
| 3 | Hay módulos pero alguno desconectado | "Módulo desconectado", ámbar | Tarjetas de módulos desconectados con `display_name`, `module_id` y última conexión (`last_seen`) |
| 4 | Algún módulo conectado con la cámara sin señal | "Cámara sin señal", ámbar | Tarjetas con `display_name` y desde cuándo no hay imagen (`camera_status_at`) |
| 5 | Todo en orden | "Protección Activa", verde | "Estado: Seguro" |

Desconectado va **antes** que cámara sin señal porque es el fallo más ambiguo: no sabemos si el módulo sigue vivo detectando y encolando alertas offline, o si está apagado. Con la cámara caída sabemos exactamente qué pasa — el módulo vive y no ve.

### Estado de cámara (`camera_ok`)

Un módulo puede estar `connected` y aun así no detectar nada porque su cámara IP dejó de entregar frames. `AlertService.isCameraDown(module)` es el único lugar donde vive esa regla:

- Solo considera ciego a un módulo **`connected`**. En uno desconectado, `camera_ok` es el último valor reportado y no dice nada del presente.
- Los documentos anteriores a este campo no lo traen y se asumen sanos.

Lo consumen el dashboard (estado 4) y `linked_cameras_screen`, donde la tarjeta del módulo tiene tres estados: `Conectado` (verde), `Sin señal` (ámbar, ícono de cámara tachada) y `Desconectado` (gris).

El dato llega solo: `linkedModulesStream()` devuelve el documento completo de Firestore, así que no hubo que tocar el stream ni la capa REST.

Debajo, "Historial de Seguridad" lista las últimas 4 alertas reales (estado/fecha verdaderos, tap → `/emergency`); "Ver todo" cambia a la pestaña Historial.

---

## Vinculación de módulos

Pantalla `linked_cameras_screen.dart`:
- **Vincular**: diálogo que pide `module_id`, **nombre visible opcional** y **URL de la cámara**, con vista previa en vivo antes de confirmar. Vincula (`POST /api/modules/link`) y luego, si se ingresaron, asigna nombre (`PATCH /api/modules/{id}/name`) y cámara (`PATCH /api/modules/{id}/camera`). Si alguno falla el módulo ya quedó vinculado y se avisa para editarlo desde la lista.
- **Renombrar** y **Cambiar cámara**: menú de tres puntos en cada tarjeta. Al cambiar la cámara la URL es obligatoria y hay que probarla antes de guardar (ver más abajo).
- **Desvincular**: **swipe-to-delete** (deslizar de derecha a izquierda) con confirmación → `POST /api/modules/unlink`. La tarjeta desaparece cuando el stream de Firestore refleja `user_id = null` (no la quita el `Dismissible`, para evitar el assert "dismissed Dismissible still in tree").

Desvincular un módulo **detiene su detección** en el servidor (push `module_unlinked` al módulo local).

Un módulo sin `camera_url` muestra "Sin cámara configurada" en ámbar: sin cámara no detecta nada, así que eso desplaza al conteo de cámaras.

---

## Vista previa de la cámara (`widgets/mjpeg_view.dart`)

`video_player` no sirve para una cámara IP: un stream MJPEG no es un video, es una respuesta HTTP infinita `multipart/x-mixed-replace` con un JPEG completo por parte. Y RTSP no se puede reproducir sin una dependencia nativa (`media_kit` / `flutter_vlc_player`).

`MjpegFrameParser` extrae los frames buscando los marcadores del propio JPEG — SOI `FF D8` y EOI `FF D9` — en vez de parsear el boundary del multipart, que cada servidor formatea distinto. Es una clase pura, sin Flutter, y por eso está cubierta por tests: los chunks de red no respetan los límites de los frames (un JPEG puede llegar partido en tres, un marcador puede partirse por la mitad entre dos chunks, y un chunk puede traer varios frames).

- `MjpegView.canPreview(url)` → solo `http`/`https`. Una URL `rtsp://` se acepta como fuente pero muestra "sin vista previa disponible".
- `ValueKey(url)` en el widget fuerza la reconexión al cambiar la URL.
- Watchdog de 8 s **solo para el primer frame**: si no llega ninguno, muestra el error en vez de un spinner eterno.
- `Image.memory(gaplessPlayback: true)` — sin eso parpadea en negro entre frames.
- `clientFactory` es inyectable. `TestWidgetsFlutterBinding` intercepta `HttpClient` y responde 400 sin salir a la red, así que **ningún widget test puede ejercitar el stream real**; hay que pasarle un cliente falso.

### Reconexión ante microcortes

Un MJPEG sobre HTTP se corta seguido (la app de la cámara cierra la conexión, el Wi-Fi hipa). El widget distingue dos casos:

| Situación | Comportamiento |
|---|---|
| El stream termina **sin** haber dado un frame | Fallo (`onFailed`). No hay nada que verificar. |
| El stream termina **después** de haber dado imagen | Reconecta con backoff (500 ms → 4 s), conserva el último frame en pantalla y muestra el aviso "Reconectando…". **No** dispara `onFailed`. |

El aviso importa: sin él, un frame congelado se ve igual que uno en vivo.

Y la verificación **se aferra**: una vez que `onLive` disparó, un corte posterior no vuelve el estado a `failed`. Haber visto la cámara es un hecho consumado; solo editar la URL lo invalida.

### Ancho fijo de los diálogos

`AlertDialog` mide su contenido con `IntrinsicWidth`, y un stream de video no tiene ancho natural. Por eso los diálogos envuelven su contenido en un `SizedBox(width: _dialogWidth)`, y `Image.memory` **no** lleva `width: double.infinity` — con él, el layout falla con `'input.isFinite': is not true`.

**Limitaciones conocidas:**
- La previsualización requiere que el **celular esté en la misma LAN que la cámara**. Es una comprobación del celular, no del módulo: la confirmación autoritativa llega cuando el módulo reporta `camera_ok` (ver `isCameraDown`).
- **No funciona en Flutter web**: `BrowserClient` bufferiza la respuesta en vez de entregarla como stream.

---

## No se guarda una cámara que no se vio (`widgets/camera_check.dart`)

El botón de confirmación de los diálogos está gobernado por `cameraSaveDecision(check, cameraOptional:)`, una función pura sobre el enum `CameraCheck`:

| Estado | Botón |
|---|---|
| `empty` | Habilitado solo si la cámara es opcional (diálogo de vincular) |
| `unchecked` — URL escrita sin probar, o editada después de probarla | **Deshabilitado** |
| `checking` — conectando | **Deshabilitado** |
| `live` — llegó un frame | Habilitado: "Guardar" |
| `failed` — se probó y falló | Habilitado: **"Guardar sin verificar"** |
| `unsupported` — `rtsp://`, no previsualizable | Habilitado: **"Guardar sin verificar"** |

`MjpegView` reporta `onLive` al primer frame y `onFailed` al primer error. Si `onFailed` no se disparara, el diálogo quedaría en `checking` y el botón bloqueado para siempre — por eso está cubierto por widget tests.

`_CameraUrlEditor` escucha al `TextEditingController`: **si la URL se edita después de una previsualización exitosa, el estado vuelve a `unchecked`**. Lo que se guarda tiene que ser lo que se vio.

**¿Por qué existe el escape "sin verificar"?** Dos casos legítimos en los que la URL es correcta y la previsualización igual no puede funcionar: RTSP (sin dependencia nativa no se reproduce) y el celular fuera de la LAN de la cámara (en datos móviles) mientras el módulo sí la alcanza desde la Wi-Fi del hogar. El botón cambia de texto en vez de desaparecer: el escape existe pero dice lo que hace.

---

## Push notifications (FCM)

- `FcmService.initialize()` se llama desde `HomeWrapper` tras login.
- El servidor envía `data.type == 'fall_detected'` con `alert_id`, `timestamp`, `clip_url`.
- Foreground / background / app cerrada → navega a `/emergency` con esos argumentos vía `navigatorKey`.
- El handler de background (`_backgroundMessageHandler` en `main.dart`) es función top-level (requisito de FCM).
- En Android se crea el canal `fall_alerts` (importancia máxima). En web se usa un `BroadcastChannel`.

---

## Configuración

| Aspecto | Valor / ubicación |
|---|---|
| URL del servidor | `kIsWeb ? http://localhost:8000 : http://10.0.2.2:8000` (en `ApiClient` y `AlertService`). `10.0.2.2` es el host desde el emulador Android |
| Firebase | `firebase_options.dart` + `android/app/google-services.json` |
| VAPID key (web push) | constante en `FcmService` / `AlertService` |

> La URL del servidor está hardcodeada para desarrollo (localhost / emulador). Para un dispositivo físico o producción habría que apuntar a la IP/host real del servidor.

---

## Rutas y navegación

- Rutas con nombre (en `main.dart`): `/register` y `/emergency`. El resto de pantallas se abren con `Navigator.push`.
- `home` se decide por `authStateChanges`: con sesión → `HomeWrapper`, sin sesión → `LoginScreen`.
- `HomeWrapper` tiene bottom nav de 3 tabs (`IndexedStack`): **Inicio** (Dashboard), **Historial**, **Ajustes**. El dashboard recibe un callback `onSeeAllHistory` para cambiar a la pestaña Historial.

---

## Estructura de pantallas

```
screens/
├── home_wrapper.dart          ← bottom nav + IndexedStack (Inicio/Historial/Ajustes)
├── dashboard_screen.dart      ← estado dinámico del hogar + historial reciente
├── history_screen.dart        ← historial completo con filtros por estado
├── emergency_alert_screen.dart← detalle de una alerta: clip + confirmar/falsa alarma
├── emergency_alerts_screen.dart
├── linked_cameras_screen.dart ← vincular/renombrar/desvincular módulos
├── login_screen.dart / register_screen.dart
├── settings_screen.dart       ← ajustes; acceso a perfil, seguridad, módulos
├── edit_profile_screen.dart / security_screen.dart
├── assisted_persons_screen.dart / help_center_screen.dart
```

---

## Modelo de alerta

`models/alert_model.dart` — `AlertModel` (`id`, `timestamp`, `status`, `location`, `elderlyName`, `description`) y `AlertStatus { detected, confirmed, falseAlarm }`.

Al leer de Firestore, el doc solo trae `alert_id`, `timestamp` (Timestamp), `status`, etc.; los campos `location`/`elderlyName`/`description` no existen y quedan en `''`. El status legacy `'pending'` cae a `detected`.

---

## Decisiones de diseño relevantes

**¿Por qué lecturas directas de Firestore y no por REST?**
El polling REST (cada 30s) retrasaba la actualización del dashboard. Con listeners `snapshots()` los cambios (alerta nueva, módulo desconectado, cambio de estado) se reflejan al instante. Las escrituras siguen por el servidor para conservar la lógica de negocio y la autorización.

**¿Por qué el swipe-to-delete devuelve `false` en `confirmDismiss`?**
La eliminación es asíncrona (REST → servidor → Firestore). Si el `Dismissible` quitara la tarjeta antes de que el stream se actualice, dispararía el assert "dismissed Dismissible still in tree". Devolviendo `false` se deja que el stream de Firestore quite la tarjeta cuando `user_id` cambia a null.

**¿Por qué los errores de `setModuleCamera` se muestran tal cual al usuario?**
El servidor valida el esquema de la URL y devuelve el motivo en `detail` (ej. "Esquema no permitido: 'file'. Usar uno de: http, https, ..."). `AlertService._detail()` lo extrae y se propaga sin reescribirlo: está redactado para el usuario final, y duplicar los mensajes en la app los desincronizaría de la validación real.

**¿Por qué `isCameraDown` exige que el módulo esté `connected`?**
En un módulo desconectado, `camera_ok` es el último valor que reportó y no dice nada del presente. Mostrar "cámara sin señal" sobre un módulo apagado sería ruido: el usuario ya ve que está desconectado, y esa es la acción que tiene que tomar.

**¿Por qué registro atómico en `AuthService`?**
Si crear el perfil en Firestore falla tras crear el usuario en Auth, se borra el usuario de Auth para no dejar cuentas huérfanas. La vinculación del módulo, en cambio, es opcional: si falla, el registro igual es exitoso (se avisa).

**¿Por qué el cambio de contraseña pasa por el servidor?**
El cliente reautentica con Firebase Auth (verifica la contraseña actual), pero el cambio efectivo lo hace el servidor con el Admin SDK (`POST /api/auth/change-password`).
