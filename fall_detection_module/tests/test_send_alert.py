"""
Tests para SendAlert.
Usa mocks para ClipRecorder, ClipStorage y AlertSender.
"""

import pytest
from datetime import datetime, timezone
from pathlib import Path

from domain.entities import Alert, FallEvent
from application.use_cases.send_alert import SendAlert
from application.ports.clip_storage import ClipStorage
from application.ports.alert_sender import AlertSender
from application.ports.clip_recorder import ClipRecorder
from application.ports.alert_queue import AlertQueue
from infrastructure.storage.local_queue import LocalAlertQueue


# ── Mocks ─────────────────────────────────────────────────────────────────────
class MockClipRecorder(ClipRecorder):
    def __init__(self, clip_path: str = "mock/clip.mp4"):
        self._clip_path = clip_path
        self._recording = False

    def add_frame(self, frame) -> None:
        pass

    def record(self, event, on_ready) -> None:
        self._recording = True
        on_ready(self._clip_path)
        self._recording = False

    def is_recording(self) -> bool:
        return self._recording

    def abort(self, reason: str) -> None:
        self._recording = False


class MockClipStorage(ClipStorage):
    def __init__(self, should_fail: bool = False):
        self.uploaded    = []
        self.should_fail = should_fail

    def upload(self, clip_path: str, clip_id: str) -> str:
        if self.should_fail:
            raise RuntimeError("Error simulado de subida")
        self.uploaded.append(clip_path)
        return f"https://mock.storage/{clip_id}.mp4"


class MockAlertSender(AlertSender):
    def __init__(self, connected: bool = True):
        self.alerts_sent = []
        self._connected  = connected

    def send(self, alert: Alert) -> bool:
        if not self._connected:
            return False
        self.alerts_sent.append(alert)
        return True

    def is_connected(self) -> bool:
        return self._connected


# ── Helpers ───────────────────────────────────────────────────────────────────
def make_event() -> FallEvent:
    return FallEvent(
        module_id=   "test-module",
        timestamp=   datetime.now(timezone.utc),
        confidence=  0.85,
        frame_count= 3,
        frames=      [],
    )

def make_send_alert(
    tmp_path,
    clip_path:    str  = "mock/clip.mp4",
    connected:    bool = True,
    upload_fails: bool = False,
) -> tuple[SendAlert, MockClipStorage, MockAlertSender, LocalAlertQueue]:
    clip_recorder = MockClipRecorder(clip_path=clip_path)
    clip_storage  = MockClipStorage(should_fail=upload_fails)
    alert_sender  = MockAlertSender(connected=connected)
    local_queue   = LocalAlertQueue(queue_path=str(tmp_path / "pending.json"))

    send_alert = SendAlert(
        clip_recorder=clip_recorder,
        clip_storage= clip_storage,
        alert_sender= alert_sender,
        alert_queue=  local_queue,
    )
    return send_alert, clip_storage, alert_sender, local_queue


# ── Tests ─────────────────────────────────────────────────────────────────────
def test_flujo_normal_envia_alerta(tmp_path):
    """Con conexión y subida exitosa, la alerta se envía al servidor."""
    send_alert, clip_storage, alert_sender, local_queue = make_send_alert(tmp_path)

    send_alert.execute(make_event())

    assert len(clip_storage.uploaded) == 1
    assert len(alert_sender.alerts_sent) == 1
    assert alert_sender.alerts_sent[0].clip_url.startswith("https://mock.storage/")
    assert local_queue.is_empty()


def test_sin_conexion_guarda_en_cola(tmp_path):
    """Sin conexión la alerta se guarda en cola local con clip_path."""
    send_alert, clip_storage, alert_sender, local_queue = make_send_alert(
        tmp_path, connected=False
    )

    send_alert.execute(make_event())

    assert len(alert_sender.alerts_sent) == 0
    assert local_queue.size() == 1
    pending = local_queue.pop_all()
    assert pending[0].clip_url is not None   # sí se subió el clip
    assert pending[0].sent == False


def test_falla_subida_guarda_en_cola(tmp_path):
    """Si la subida al bucket falla, la alerta se guarda en cola local sin clip_url."""
    send_alert, clip_storage, alert_sender, local_queue = make_send_alert(
        tmp_path, upload_fails=True
    )

    send_alert.execute(make_event())

    assert len(alert_sender.alerts_sent) == 0
    assert local_queue.size() == 1
    pending = local_queue.pop_all()
    assert pending[0].clip_url is None    # no se pudo subir
    assert pending[0].clip_path is not None


def test_flush_pending_envia_alertas(tmp_path):
    """flush_pending reenvía las alertas pendientes cuando hay conexión."""
    # Primero guardar alerta sin conexión
    send_alert, _, alert_sender, local_queue = make_send_alert(
        tmp_path, connected=False
    )
    send_alert.execute(make_event())
    assert local_queue.size() == 1

    # Reconectar
    send_alert.set_alert_sender(MockAlertSender(connected=True))
    sent = send_alert.flush_pending()

    assert sent == 1
    assert local_queue.is_empty()


def test_flush_pending_sin_conexion_no_hace_nada(tmp_path):
    """flush_pending sin conexión no envía nada."""
    send_alert, _, _, local_queue = make_send_alert(tmp_path, connected=False)
    send_alert.execute(make_event())
    assert local_queue.size() == 1

    sent = send_alert.flush_pending()

    assert sent == 0
    assert local_queue.size() == 1


def test_flush_pending_sube_clip_sin_url(tmp_path):
    """flush_pending sube el clip si clip_url es None antes de reenviar."""
    # Guardar alerta con subida fallida
    send_alert, _, _, local_queue = make_send_alert(
        tmp_path, upload_fails=True, connected=False
    )
    send_alert.execute(make_event())

    pending = local_queue.pop_all()
    assert pending[0].clip_url is None

    # Volver a poner en cola manualmente
    local_queue.push(pending[0])

    # Reconectar con storage que ahora sí funciona
    new_storage = MockClipStorage(should_fail=False)
    new_sender  = MockAlertSender(connected=True)
    send_alert.set_alert_sender(new_sender)
    send_alert._clip_storage = new_storage

    sent = send_alert.flush_pending()

    assert sent == 1
    assert len(new_storage.uploaded) == 1
    assert local_queue.is_empty()