"""
Tests para OpenCVClipRecorder.abort() — el corte de cámara en medio de una grabación.

Usa frames sintéticos: no dependen del dataset, así que corren siempre.
"""

import threading
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import pytest

from domain.entities import FallEvent
from infrastructure.video.opencv_clip_recorder import OpenCVClipRecorder

CONTEXT_BEFORE = 10
CONTEXT_AFTER  = 20


@pytest.fixture
def recorder(tmp_path):
    return OpenCVClipRecorder(
        clips_dir=      str(tmp_path),
        context_before= CONTEXT_BEFORE,
        context_after=  CONTEXT_AFTER,
        fps=            25.0,
    )


def frame(value: int = 0) -> np.ndarray:
    return np.full((48, 64, 3), value, dtype=np.uint8)


def make_event() -> FallEvent:
    return FallEvent(
        module_id=   "test",
        timestamp=   datetime.now(timezone.utc),
        confidence=  0.87,
        frame_count= 3,
        frames=      [],
    )


def _start_recording(recorder, on_ready) -> None:
    """Llena el buffer, confirma una caída y entrega frames posteriores parciales."""
    for i in range(CONTEXT_BEFORE):
        recorder.add_frame(frame(i))
    recorder.record(make_event(), on_ready)
    for i in range(CONTEXT_AFTER // 4):   # se corta antes de llegar a context_after
        recorder.add_frame(frame(100 + i))


def test_abort_libera_el_grabador_trabado(recorder):
    """
    Regresión: si la cámara se corta durante una grabación, los context_after
    frames nunca llegan y el grabador queda trabado en is_recording() para
    siempre, descartando toda caída posterior.
    """
    _start_recording(recorder, on_ready=lambda p: None)
    assert recorder.is_recording()   # esperando frames que nunca llegarán

    recorder.abort("corte de cámara")

    assert not recorder.is_recording()

    # Y acepta una grabación nueva tras reconectar.
    for i in range(CONTEXT_BEFORE):
        recorder.add_frame(frame(i))
    recorder.record(make_event(), on_ready=lambda p: None)
    assert recorder.is_recording()


def test_abort_entrega_el_clip_parcial(recorder):
    """
    La caída ya fue confirmada: su alerta debe salir aunque el clip sea corto.
    abort() cierra el archivo e invoca on_ready.
    """
    ready = threading.Event()
    paths = []

    _start_recording(recorder, on_ready=lambda p: (paths.append(p), ready.set()))
    recorder.abort("corte de cámara")

    assert ready.wait(timeout=2.0), "on_ready no se invocó — la alerta se perdería"
    clip = Path(paths[0])
    assert clip.exists() and clip.stat().st_size > 0

    cap = cv2.VideoCapture(str(clip))
    assert cap.isOpened(), "el clip parcial no es legible"
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    assert frames > 0


def test_abort_descarta_el_buffer_de_contexto(recorder):
    """
    Los frames previos al corte no deben empalmarse con los posteriores:
    producirían un clip con un salto temporal invisible.
    """
    for i in range(CONTEXT_BEFORE):
        recorder.add_frame(frame(i))
    assert len(recorder._buffer) == CONTEXT_BEFORE

    recorder.abort("corte de cámara")

    assert len(recorder._buffer) == 0


def test_abort_sin_grabacion_en_curso_es_inocuo(recorder):
    """abort() se llama en cada corte, haya o no grabación activa."""
    recorder.abort("corte de cámara")
    assert not recorder.is_recording()
