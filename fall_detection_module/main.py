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
import sys
import threading
import time

import config
from domain.fall_service import FallDetectionService
from application.use_cases.detect_fall import DetectFall
from application.use_cases.send_alert import SendAlert
from application.use_cases.manage_camera import ManageCamera
from infrastructure.detector.yolo_pose import YoloPoseExtractor
from infrastructure.detector.lstm_model import LSTMFallPredictor
from infrastructure.video.opencv_clip_recorder import OpenCVClipRecorder
from infrastructure.video.opencv_camera import OpenCVCamera
from infrastructure.video.opencv_camera_scanner import OpenCVCameraScanner
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
def detection_thread(detect_fall, clip_recorder, active_cam):
    logger.info("Thread 1 iniciado")
    detect_fall.reset()

    REMINDER_INTERVAL = 30   # segundos entre recordatorios mientras espera vinculación
    waiting       = False
    last_reminder = 0.0

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

        frame = active_cam.instance.read()
        if frame is None:
            logger.info("Video terminado — deteniendo módulo")
            stop_event.set()   # ← detener todo
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
    source = config.get_camera_source()

    if isinstance(source, str):
        # Fuente de video — no escanear cámaras físicas
        active_cam   = ActiveCamera(OpenCVCamera(source))
        cameras_dict = [{"id": 0, "name": "Video simulado"}]
        logger.info(f"Fuente de video: {source}")
    else:
        # Cámara física — escanear y seleccionar
        manage_camera = ManageCamera(scanner=OpenCVCameraScanner())
        cameras = manage_camera.scan_cameras()
        if not cameras:
            logger.error("No se encontraron cámaras disponibles")
            sys.exit(1)
        cameras_dict = [{"id": c.id, "name": c.name} for c in cameras]
        manage_camera.set_camera(cameras[0].id)
        active_cam = ActiveCamera(OpenCVCamera(cameras[0].id))
        logger.info(f"Cámara activa: {cameras[0].name}")

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
    def on_set_camera(camera_id: int):
        logger.info(f"Cambiando a cámara {camera_id}")
        active_cam.switch(camera_id)
        detect_fall.reset()
        manage_camera.set_camera(camera_id)

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
        server_url=       ws_url,
        module_id=        config.MODULE_ID,
        cameras=          cameras_dict,
        on_set_camera=    on_set_camera,
        on_config_update= on_config_update,
        on_link_status=   on_link_status,
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
    t1 = threading.Thread(
        target=detection_thread,
        args=(detect_fall, clip_recorder, active_cam),
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

    logger.info("Módulo detenido")

    logger.info("Módulo detenido")


if __name__ == "__main__":
    main()