"""
Tests para OpenCVClipRecorder.
Usa un video real para verificar el buffer circular y la grabación del clip.

Requiere:
    - tests/videos/Office/Fall/video (1).avi
"""

import pytest
import cv2
import time
import threading
from pathlib import Path
from datetime import datetime, timezone

from domain.entities import FallEvent
from infrastructure.video.opencv_clip_recorder import OpenCVClipRecorder

# ── Rutas ─────────────────────────────────────────────────────────────────────
VIDEO_PATH = Path("tests/videos/Office/Fall/video (1).avi")

pytestmark = pytest.mark.skipif(
    not VIDEO_PATH.exists(),
    reason="Video de prueba no encontrado"
)


# ── Fixture ───────────────────────────────────────────────────────────────────
@pytest.fixture
def recorder(tmp_path):
    return OpenCVClipRecorder(
        clips_dir=      "tests/clips_output",
        context_before= 25,   # ~1s a 25fps
        context_after=  25,   # ~1s a 25fps
        fps=            25.0,
    )


def make_event(frames: list) -> FallEvent:
    return FallEvent(
        module_id=   "test",
        timestamp=   datetime.now(timezone.utc),
        confidence=  0.87,
        frame_count= 3,
        frames=      frames,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────
def test_recorder_inicia_sin_grabar(recorder):
    assert not recorder.is_recording()


def test_buffer_acumula_frames(recorder):
    """Verifica que add_frame acumula frames en el buffer circular."""
    cap = cv2.VideoCapture(str(VIDEO_PATH))
    frames_leidos = 0

    for _ in range(30):
        ret, frame = cap.read()
        if not ret:
            break
        recorder.add_frame(frame)
        frames_leidos += 1

    cap.release()
    # El buffer tiene maxlen=context_before=25, entonces guarda los últimos 25
    assert frames_leidos == 30
    assert len(recorder._buffer) == 25


def test_record_crea_archivo_mp4(recorder, tmp_path):
    """Verifica que record() crea un archivo .mp4 válido."""
    cap = cv2.VideoCapture(str(VIDEO_PATH))
    clip_path_result = []
    event_ready      = threading.Event()

    def on_ready(clip_path):
        clip_path_result.append(clip_path)
        event_ready.set()

    # Llenar buffer con frames
    for _ in range(30):
        ret, frame = cap.read()
        if not ret:
            break
        recorder.add_frame(frame)

    # Confirmar caída
    event = make_event([])
    recorder.record(event, on_ready)
    assert recorder.is_recording()

    # Agregar context_after frames para cerrar el clip
    for _ in range(30):
        ret, frame = cap.read()
        if not ret:
            break
        recorder.add_frame(frame)
        if event_ready.is_set():
            break

    cap.release()

    # Esperar callback con timeout
    event_ready.wait(timeout=5.0)

    assert len(clip_path_result) == 1
    clip_path = Path(clip_path_result[0])
    assert clip_path.exists()
    assert clip_path.suffix == ".mp4"
    assert clip_path.stat().st_size > 0
    print(f"\nClip grabado: {clip_path} ({clip_path.stat().st_size / 1024:.1f} KB)")


def test_record_clip_tiene_frames(recorder, tmp_path):
    """Verifica que el clip grabado tiene frames legibles."""
    cap = cv2.VideoCapture(str(VIDEO_PATH))
    clip_path_result = []
    event_ready      = threading.Event()

    def on_ready(clip_path):
        clip_path_result.append(clip_path)
        event_ready.set()

    for _ in range(30):
        ret, frame = cap.read()
        if not ret:
            break
        recorder.add_frame(frame)

    recorder.record(make_event([]), on_ready)

    for _ in range(30):
        ret, frame = cap.read()
        if not ret:
            break
        recorder.add_frame(frame)
        if event_ready.is_set():
            break

    cap.release()
    event_ready.wait(timeout=5.0)

    # Verificar que el clip se puede leer con OpenCV
    clip = cv2.VideoCapture(clip_path_result[0])
    assert clip.isOpened()
    frame_count = int(clip.get(cv2.CAP_PROP_FRAME_COUNT))
    clip.release()

    assert frame_count > 0
    print(f"\nFrames en el clip: {frame_count}")


def test_no_graba_dos_clips_simultaneos(recorder):
    """Verifica que una segunda llamada a record() mientras graba se ignora."""
    cap = cv2.VideoCapture(str(VIDEO_PATH))
    callbacks_llamados = []

    for _ in range(30):
        ret, frame = cap.read()
        if not ret:
            break
        recorder.add_frame(frame)

    recorder.record(make_event([]), lambda p: callbacks_llamados.append("first"))
    recorder.record(make_event([]), lambda p: callbacks_llamados.append("second"))

    # Agregar frames para cerrar el primer clip
    for _ in range(30):
        ret, frame = cap.read()
        if not ret:
            break
        recorder.add_frame(frame)

    cap.release()
    time.sleep(0.5)

    # Solo debe haberse llamado el primer callback
    assert "second" not in callbacks_llamados