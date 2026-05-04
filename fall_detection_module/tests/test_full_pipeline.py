"""
Test de integración completo: detección real + grabación de clip.
YOLO + LSTM + FallService → FallEvent → ClipRecorder → clip.mp4

No usa S3 ni WebSocket — usa mocks para ClipStorage y AlertSender.
"""

import pytest
import cv2
import threading
import time
from pathlib import Path
from collections import deque
from datetime import datetime, timezone

from domain.entities import Alert
from domain.fall_service import FallDetectionService
from domain.value_objects import KeypointsSequence
from application.ports.clip_storage import ClipStorage
from application.ports.alert_sender import AlertSender
from application.ports.alert_queue import AlertQueue
from application.use_cases.detect_fall import DetectFall
from application.use_cases.send_alert import SendAlert
from infrastructure.detector.yolo_pose import YoloPoseExtractor
from infrastructure.detector.lstm_model import LSTMFallPredictor
from infrastructure.video.opencv_clip_recorder import OpenCVClipRecorder
from infrastructure.storage.local_queue import LocalAlertQueue

# ── Rutas ─────────────────────────────────────────────────────────────────────
YOLO_PATH  = Path("models/yolo11x-pose.pt")
LSTM_PATH  = Path("models/fall_lstm_final.pt")
VIDEO_PATH = Path("tests/videos/Office/Fall/video (9).avi")

pytestmark = pytest.mark.skipif(
    not YOLO_PATH.exists() or not LSTM_PATH.exists() or not VIDEO_PATH.exists(),
    reason="Modelos o video no encontrados"
)


# ── Mocks ─────────────────────────────────────────────────────────────────────
class MockClipStorage(ClipStorage):
    def __init__(self):
        self.uploaded = []

    def upload(self, clip_path: str, clip_id: str) -> str:
        self.uploaded.append(clip_path)
        return f"https://mock.storage/{clip_id}.mp4"


class MockAlertSender(AlertSender):
    def __init__(self):
        self.alerts_sent = []

    def send(self, alert: Alert) -> bool:
        self.alerts_sent.append(alert)
        return True

    def is_connected(self) -> bool:
        return True


# ── Fixtures ──────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def yolo_extractor():
    return YoloPoseExtractor(
        model_path=str(YOLO_PATH),
        conf=0.8,
        device="cuda:0",
    )

@pytest.fixture(scope="module")
def lstm_predictor():
    return LSTMFallPredictor(
        model_path=str(LSTM_PATH),
        device="cuda:0",
    )


# ── Test ──────────────────────────────────────────────────────────────────────
def test_flujo_completo_deteccion_y_clip(yolo_extractor, lstm_predictor, tmp_path):
    """
    Flujo completo:
      1. YOLO + LSTM detectan caída real en video
      2. ClipRecorder graba el clip con contexto
      3. MockClipStorage simula la subida
      4. MockAlertSender simula el envío
      5. Verificar clip en disco y alerta con clip_url
    """
    # ── Infraestructura ───────────────────────────────────────────────────
    clip_storage  = MockClipStorage()
    alert_sender  = MockAlertSender()
    clip_recorder = OpenCVClipRecorder(
        clips_dir=      "tests/clips_output",
        context_before= 50,
        context_after=  25,
        fps=            25.0,
    )
    local_queue = LocalAlertQueue(
        queue_path=str(tmp_path / "pending.json")
    )

    # ── Dominio ───────────────────────────────────────────────────────────
    fall_service = FallDetectionService(
        module_id=     "test",
        min_frames=    3,
        conf_lstm=     0.7,
        alert_cooldown=30,
    )

    # ── Casos de uso ──────────────────────────────────────────────────────
    detect_fall = DetectFall(
        extractor=    yolo_extractor,
        predictor=    lstm_predictor,
        fall_service= fall_service,
    )
    send_alert = SendAlert(
        clip_recorder=clip_recorder,
        clip_storage= clip_storage,
        alert_sender= alert_sender,
        alert_queue=  local_queue,
    )

    # ── Correr video ──────────────────────────────────────────────────────
    cap        = cv2.VideoCapture(str(VIDEO_PATH))
    fall_event = None
    frame_idx  = 0
    alert_received = threading.Event()

    # Monkey-patch on_ready para saber cuando el clip está listo
    original_execute = send_alert.execute
    def execute_with_signal(event):
        original_on_ready = send_alert._on_clip_ready
        def patched_on_ready(ev, clip_id, clip_path):
            original_on_ready(ev, clip_id, clip_path)
            alert_received.set()
        send_alert._on_clip_ready = lambda ev, cid, cp: patched_on_ready(ev, cid, cp)
        original_execute(event)
    send_alert.execute = execute_with_signal

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1

        clip_recorder.add_frame(frame)
        event = detect_fall.execute(frame)

        if event is not None and fall_event is None:
            fall_event = event
            print(f"\nCaída detectada en frame {frame_idx} | conf={event.confidence:.3f}")
            send_alert.execute(event)

        # Seguir leyendo frames para context_after
        if fall_event is not None and alert_received.is_set():
            break

    # Leer frames adicionales para context_after si el clip no terminó
    if fall_event is not None and not alert_received.is_set():
        for _ in range(100):
            ret, frame = cap.read()
            if not ret:
                break
            clip_recorder.add_frame(frame)
            if alert_received.is_set():
                break

    cap.release()
    alert_received.wait(timeout=10.0)

    # ── Verificaciones ────────────────────────────────────────────────────
    assert fall_event is not None, "No se detectó ninguna caída"

    # El clip fue grabado en disco
    assert len(clip_storage.uploaded) == 1
    clip_path = Path(clip_storage.uploaded[0])
    assert clip_path.exists(), f"Clip no encontrado en disco: {clip_path}"
    assert clip_path.stat().st_size > 0

    # El clip es un video válido
    cap_clip = cv2.VideoCapture(str(clip_path))
    assert cap_clip.isOpened()
    frame_count = int(cap_clip.get(cv2.CAP_PROP_FRAME_COUNT))
    cap_clip.release()
    assert frame_count > 0
    print(f"Clip grabado: {clip_path.name} ({frame_count} frames, {clip_path.stat().st_size/1024:.1f} KB)")

    # La alerta fue enviada con clip_url
    assert len(alert_sender.alerts_sent) == 1
    alert = alert_sender.alerts_sent[0]
    assert alert.clip_url is not None
    assert alert.clip_url.startswith("https://mock.storage/")
    assert alert.confidence >= 0.7
    print(f"Alerta enviada: clip_url={alert.clip_url}")