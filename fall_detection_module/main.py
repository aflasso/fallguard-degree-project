"""
Punto de entrada del módulo de detección de caídas.
Orquesta los 3 threads y conecta todas las capas.

Thread 1 — Detección (loop principal)
Thread 2 — Uploader (graba y sube clips)
Thread 3 — WebSocket (comunicación con servidor)
"""

import logging
import queue
import signal
import threading
import time

import config
from domain.fall_service import FallDetectionService
from application.use_cases.detect_fall import DetectFall
from application.use_cases.send_alert import SendAlert
from infrastructure.detector.yolo_pose import YoloPoseExtractor
from infrastructure.detector.lstm_model import LSTMFallPredictor
from infrastructure.video.opencv_clip_recorder import OpenCVClipRecorder
from infrastructure.video.active_camera import ActiveCamera
from infrastructure.storage.local_queue import LocalAlertQueue
from infrastructure.comms.s3_uploader import S3ClipUploader
from infrastructure.comms.ws_client import WebSocketClient


# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s [%(threadName)s] %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Colas de comunicación entre threads ───────────────────────────────────────
clip_queue  = queue.Queue()   # Thread 1 → Thread 2: FallEvent
alert_queue = queue.Queue()   # Thread 2 → Thread 3: Alert

# ── Stop event global ─────────────────────────────────────────────────────────
stop_event = threading.Event()

# ── Linked event global ───────────────────────────────────────────────────────
# La detección solo corre cuando el módulo está vinculado a un usuario.
# El servidor es la fuente de verdad: marca/limpia este evento via WebSocket
# (mensaje 'connected' con flag 'linked', y 'module_linked' / 'module_unlinked').
linked_event = threading.Event()


# ──────────────────────────────────────────────────────────────────────────────
# Thread 1 — Detección
# ──────────────────────────────────────────────────────────────────────────────
def detection_thread(detect_fall, clip_recorder, active_cam, report_camera_status):
    logger.info("Thread 1 iniciado")
    detect_fall.reset()

    REMINDER_INTERVAL = 30   # segundos entre recordatorios mientras espera vinculación
    OPEN_MAX_BACKOFF  = 30.0 # segundos máximo entre reintentos de apertura
    waiting        = False
    last_reminder  = 0.0
    no_source_since = 0.0
    open_backoff   = 1.0

    while not stop_event.is_set():
        # ── Gate: no detectar si el módulo no está vinculado a un usuario ──
        if not linked_event.is_set():
            now = time.monotonic()
            if not waiting:
                logger.info(
                    f"Módulo no vinculado a ningún usuario — detección en espera "
                    f"hasta que se vincule | module_id={config.MODULE_ID}"
                )
                waiting       = True
                last_reminder = now
            elif now - last_reminder >= REMINDER_INTERVAL:
                logger.info(
                    f"Esperando vinculación a un usuario para iniciar la detección "
                    f"| module_id={config.MODULE_ID}"
                )
                last_reminder = now
            linked_event.wait(timeout=5.0)   # re-chequea stop_event periódicamente
            continue

        if waiting:
            logger.info(
                f"Módulo vinculado — iniciando detección | module_id={config.MODULE_ID}"
            )
            detect_fall.reset()   # ventana deslizante limpia al arrancar
            waiting = False

        # ── Gate: sin fuente de cámara configurada desde la app ────────────
        if not active_cam.has_source():
            now = time.monotonic()
            if now - no_source_since >= REMINDER_INTERVAL:
                logger.info(
                    f"Sin fuente de cámara configurada — asignar una desde la app "
                    f"| module_id={config.MODULE_ID}"
                )
                no_source_since = now
            stop_event.wait(timeout=5.0)
            continue

        # ── Apertura / cambio de fuente ────────────────────────────────────
        # Solo Thread 1 abre y cierra la cámara: hacerlo desde Thread 3 mientras
        # hay un read() en vuelo puede segfaultear (cv2 no es thread-safe).
        if active_cam.needs_open():
            clip_recorder.abort("cambio de fuente")
            detect_fall.reset()
            if active_cam.open():
                open_backoff = 1.0
                report_camera_status(True, "")
            else:
                report_camera_status(False, "no se pudo abrir la fuente")
                logger.warning(f"Reintentando apertura en {open_backoff:.0f}s...")
                stop_event.wait(timeout=open_backoff)
                open_backoff = min(open_backoff * 2, OPEN_MAX_BACKOFF)
            continue

        cam = active_cam.instance
        if cam is None:
            continue   # Thread 3 pidió otra fuente entre el open() y este read()

        frame = cam.read()
        if frame is None:
            if cam.is_stream:
                # Stream de red: un None es un corte temporal — reconectar sin
                # matar el módulo. Bloquea aquí (no hay nada que detectar) pero
                # respeta stop_event para poder apagar limpiamente.
                # El None puede venir de un corte franco o del timeout de lectura
                # que dispara una cámara congelada; ambos se tratan igual.
                stall_started = time.monotonic()
                logger.error(
                    f"Cámara sin frames hace {cam.seconds_since_last_frame():.1f}s "
                    f"— detección detenida, reconectando..."
                )
                # Sin frames, una grabación en curso nunca terminaría y el
                # grabador quedaría trabado, descartando toda caída posterior.
                clip_recorder.abort("corte de cámara")
                report_camera_status(False, "sin frames")
                # La reconexión se cancela también si el usuario eligió otra
                # cámara desde la app: no tiene sentido insistir con la vieja.
                if cam.reconnect(
                    lambda: not stop_event.is_set() and not active_cam.needs_open()
                ):
                    logger.info(
                        f"Cámara recuperada tras {time.monotonic() - stall_started:.1f}s "
                        f"sin detección"
                    )
                    report_camera_status(True, "")
                    detect_fall.reset()   # ventana limpia tras el corte
                    continue
                if active_cam.needs_open():
                    logger.info("Reconexión cancelada — hay una fuente nueva")
                    continue
                break   # cancelado por stop_event
            # Archivo/cámara local: None es fin de la fuente → detener todo
            logger.info("Video terminado — deteniendo módulo")
            stop_event.set()
            break

        clip_recorder.add_frame(frame)
        fall_event = detect_fall.execute(frame)
        if fall_event is not None:
            logger.info("Caida confirmada — enviando a clip_queue")
            clip_queue.put(fall_event)

    logger.info("Thread 1 detenido")


# ──────────────────────────────────────────────────────────────────────────────
# Thread 2 — Uploader
# ──────────────────────────────────────────────────────────────────────────────
def uploader_thread(send_alert: SendAlert):
    logger.info("Thread 2 iniciado")

    while not stop_event.is_set():
        try:
            fall_event = clip_queue.get(timeout=1.0)
            logger.info(f"Procesando FallEvent: {fall_event.timestamp}")
            send_alert.execute(fall_event)
        except queue.Empty:
            continue
        except Exception as e:
            logger.error(f"Error en uploader: {e}")

    logger.info("Thread 2 detenido")


# ──────────────────────────────────────────────────────────────────────────────
# Thread 3 — WebSocket
# ──────────────────────────────────────────────────────────────────────────────
def websocket_thread(
    ws_client:  WebSocketClient,
    send_alert: SendAlert,
):
    logger.info("Thread 3 iniciado")

    def on_reconnect():
        logger.info("Reconectado — vaciando cola local")
        sent = send_alert.flush_pending()
        logger.info(f"Alertas pendientes enviadas: {sent}")

    def alert_sender_loop():
        while not stop_event.is_set():
            try:
                alert = alert_queue.get(timeout=1.0)
                send_alert._dispatch(alert)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error enviando alerta: {e}")

    threading.Thread(
        target=alert_sender_loop,
        name="AlertSender",
        daemon=True,
    ).start()

    ws_client.run(on_reconnect=on_reconnect)
    logger.info("Thread 3 detenido")


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────
_STREAM_SCHEMES = ("rtsp://", "rtmp://", "http://", "https://", "udp://", "tcp://")


def _camera_display_name(source) -> str:
    """Nombre que ve el usuario en la app. Nunca incluye la URL."""
    if source is None:
        return "Sin cámara"
    if isinstance(source, int):
        return "Cámara local"
    if source.lower().startswith(_STREAM_SCHEMES):
        return "Cámara IP"
    return "Video de prueba"


def main():
    logger.info(f"Iniciando módulo | module_id={config.MODULE_ID}")

    # ── Restaurar estado de vinculación persistido ────────────────────────
    # Permite que un módulo ya vinculado siga detectando tras un reinicio offline.
    # El servidor lo re-afirma al reconectar (mensaje 'connected').
    if config.load_linked_state():
        linked_event.set()
        logger.info(f"Estado de vinculación restaurado: VINCULADO | module_id={config.MODULE_ID}")
    else:
        logger.info(f"Estado de vinculación: NO vinculado | module_id={config.MODULE_ID}")

    # ── Gestión de cámara ─────────────────────────────────────────────────
    # La fuente la elige el usuario desde la app; el servidor la empuja por
    # WebSocket. Aquí solo se resuelve el valor de arranque (persistido o env).
    # El módulo NO muere si no hay fuente o si no abre: Thread 1 espera y
    # reintenta, igual que espera la vinculación.
    source = config.resolve_camera_source()

    active_cam = ActiveCamera(
        source,
        open_timeout_ms=config.CAMERA_OPEN_TIMEOUT_MS,
        read_timeout_ms=config.CAMERA_READ_TIMEOUT_MS,
    )

    if source is None:
        logger.info("Sin fuente de cámara — esperando configuración desde la app")
    else:
        logger.info(f"Fuente de video de arranque: {source}")

    # El nombre viaja al servidor y es lo que muestra la app. No incluye la URL:
    # puede llevar credenciales (rtsp://usuario:clave@host).
    cameras_dict = [{"id": 0, "name": _camera_display_name(source)}]

    # ── Infraestructura ───────────────────────────────────────────────────
    yolo_extractor = YoloPoseExtractor(
        model_path=config.YOLO_MODEL_PATH,
        conf=      config.CONF_YOLO,
        device=    config.DEVICE,
    )
    lstm_predictor = LSTMFallPredictor(
        model_path=config.LSTM_MODEL_PATH,
        device=    config.DEVICE,
    )
    clip_recorder = OpenCVClipRecorder(
        clips_dir=      config.CLIPS_DIR,
        context_before= config.CONTEXT_BEFORE,
        context_after=  config.CONTEXT_AFTER,
        fps=            config.VIDEO_FPS,
    )
    local_queue = LocalAlertQueue(
        queue_path=config.LOCAL_QUEUE_PATH,
    )
    s3_uploader = S3ClipUploader()

    # ── Dominio ───────────────────────────────────────────────────────────
    fall_service = FallDetectionService(
        module_id=     config.MODULE_ID,
        min_frames=    config.MIN_FRAMES,
        conf_lstm=     config.CONF_LSTM,
        alert_cooldown=config.ALERT_COOLDOWN,
    )

    # ── Casos de uso ──────────────────────────────────────────────────────
    detect_fall = DetectFall(
        extractor=    yolo_extractor,
        predictor=    lstm_predictor,
        fall_service= fall_service,
    )

    # send_alert se crea sin alert_sender — se inyecta después
    send_alert = SendAlert(
        clip_recorder=clip_recorder,
        clip_storage= s3_uploader,
        alert_sender= None,
        alert_queue=  local_queue,
    )

    # ── Callbacks del WebSocket ───────────────────────────────────────────
    def on_set_camera_source(url: str):
        # Corre en Thread 3: solo persiste y solicita. La apertura la hace
        # Thread 1 — cv2 no es thread-safe y podría haber un read() en vuelo.
        config.save_camera_source(url)
        active_cam.request_source(url)

    def on_set_camera(camera_id: int):
        # Vestigial: selección de cámara física por índice.
        logger.info(f"Cambiando a cámara {camera_id}")
        active_cam.request_source(camera_id)

    def on_config_update(config_data: dict):
        logger.info(f"Configuración actualizada: {config_data}")
        # Por ahora solo log — requiere reinicio para aplicar

    def on_link_status(linked: bool):
        # El servidor reporta el estado de vinculación: habilita o pausa la detección.
        # No se limpia al desconectarse — un módulo ya vinculado debe seguir detectando
        # offline; solo el servidor cambia este estado de forma explícita.
        if linked:
            if not linked_event.is_set():
                logger.info(
                    f"Servidor reporta módulo VINCULADO — detección habilitada "
                    f"| module_id={config.MODULE_ID}"
                )
                config.save_linked_state(True)
            linked_event.set()
        else:
            if linked_event.is_set():
                logger.info(
                    f"Servidor reporta módulo NO vinculado — detección pausada "
                    f"| module_id={config.MODULE_ID}"
                )
                config.save_linked_state(False)
            linked_event.clear()

    # ── WebSocket ─────────────────────────────────────────────────────────
    ws_url = config.SERVER_WS_URL
    if config.MODULE_API_KEY:
        ws_url = f"{config.SERVER_WS_URL}?api_key={config.MODULE_API_KEY}"

    ws_client = WebSocketClient(
        server_url=           ws_url,
        module_id=            config.MODULE_ID,
        cameras=              cameras_dict,
        on_set_camera=        on_set_camera,
        on_config_update=     on_config_update,
        on_link_status=       on_link_status,
        on_set_camera_source= on_set_camera_source,
    )

    # Inyectar ws_client en send_alert via setter
    send_alert.set_alert_sender(ws_client)

    # ── Signal handler para Ctrl+C ────────────────────────────────────────
    def signal_handler(sig, frame):
        logger.info("Señal de parada recibida")
        stop_event.set()
        ws_client.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # ── Lanzar threads ────────────────────────────────────────────────────
    def report_camera_status(camera_ok: bool, reason: str = "") -> None:
        if not ws_client.send_camera_status(camera_ok, reason):
            logger.warning(
                "Estado de cámara no reportado (sin conexión) — se re-afirma al reconectar"
            )

    t1 = threading.Thread(
        target=detection_thread,
        args=(detect_fall, clip_recorder, active_cam, report_camera_status),
        name="Detection",
        daemon=True,
    )
    t2 = threading.Thread(
        target=uploader_thread,
        args=(send_alert,),
        name="Uploader",
        daemon=True,
    )
    t3 = threading.Thread(
        target=websocket_thread,
        args=(ws_client, send_alert),
        name="WebSocket",
        daemon=True,
    )

    t1.start()
    t2.start()
    t3.start()

    logger.info("Módulo corriendo — Ctrl+C para detener")

    # Esperar hasta que stop_event se active
    try:
        while not stop_event.is_set():
            stop_event.wait(timeout=1.0)
    except KeyboardInterrupt:
        logger.info("Ctrl+C recibido")
        stop_event.set()
        ws_client.stop()

    t1.join(timeout=5.0)   # que Thread 1 salga de read() antes de liberar la cámara
    active_cam.release()
    logger.info("Módulo detenido")

    logger.info("Módulo detenido")


if __name__ == "__main__":
    main()