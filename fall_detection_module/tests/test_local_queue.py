"""
Tests para LocalAlertQueue.
Verifica que la cola local persiste alertas en disco correctamente.
"""

import pytest
import os
from datetime import datetime, timezone
from pathlib import Path

from domain.entities import Alert
from infrastructure.storage.local_queue import LocalAlertQueue


# ── Fixture ───────────────────────────────────────────────────────────────────
@pytest.fixture
def queue(tmp_path):
    """Crea una cola temporal para cada test — se elimina al terminar."""
    queue_path = tmp_path / "test_alerts.json"
    return LocalAlertQueue(queue_path=str(queue_path))


def make_alert(clip_id: str = "test-clip-1", clip_path: str = None) -> Alert:
    return Alert(
        module_id=  "module-test",
        timestamp=  datetime.now(timezone.utc),
        confidence= 0.87,
        clip_id=    clip_id,
        clip_path=  clip_path or f"data/clips/{clip_id}.mp4",
        clip_url=   f"https://storage.example.com/{clip_id}.mp4",
        sent=       False,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────
def test_queue_inicia_vacia(queue):
    assert queue.is_empty()
    assert queue.size() == 0


def test_push_agrega_alerta(queue):
    queue.push(make_alert())
    assert not queue.is_empty()
    assert queue.size() == 1


def test_push_multiples_alertas(queue):
    queue.push(make_alert("clip-1"))
    queue.push(make_alert("clip-2"))
    queue.push(make_alert("clip-3"))
    assert queue.size() == 3


def test_pop_all_retorna_todas(queue):
    queue.push(make_alert("clip-1"))
    queue.push(make_alert("clip-2"))

    alerts = queue.pop_all()
    assert len(alerts) == 2
    assert alerts[0].clip_id == "clip-1"
    assert alerts[1].clip_id == "clip-2"


def test_pop_all_vacia_la_cola(queue):
    queue.push(make_alert())
    queue.pop_all()
    assert queue.is_empty()


def test_pop_all_cola_vacia_retorna_lista_vacia(queue):
    alerts = queue.pop_all()
    assert alerts == []


def test_persistencia_en_disco(tmp_path):
    """Verifica que las alertas sobreviven a una nueva instancia de la cola."""
    queue_path = str(tmp_path / "persistent_alerts.json")

    # Primera instancia — guarda una alerta
    q1 = LocalAlertQueue(queue_path=queue_path)
    q1.push(make_alert("clip-persistente"))

    # Segunda instancia — lee del mismo archivo
    q2 = LocalAlertQueue(queue_path=queue_path)
    assert q2.size() == 1
    alerts = q2.pop_all()
    assert alerts[0].clip_id == "clip-persistente"


def test_alerta_conserva_datos(queue):
    """Verifica que los datos de la alerta se serializan y deserializan correctamente."""
    original = make_alert("clip-datos")
    queue.push(original)

    recovered = queue.pop_all()[0]

    assert recovered.module_id  == original.module_id
    assert recovered.clip_id    == original.clip_id
    assert recovered.clip_url   == original.clip_url
    assert recovered.confidence == original.confidence
    assert recovered.sent       == original.sent

def test_alerta_sin_conexion_guarda_clip_path(queue):
    """Verifica que una alerta sin clip_url pero con clip_path se guarda correctamente."""
    alert = Alert(
        module_id=  "module-test",
        timestamp=  datetime.now(timezone.utc),
        confidence= 0.87,
        clip_id=    "clip-sin-url",
        clip_path=  "data/clips/clip-sin-url.mp4",
        clip_url=   None,   # no se pudo subir
        sent=       False,
    )
    queue.push(alert)

    recovered = queue.pop_all()[0]
    assert recovered.clip_url  is None
    assert recovered.clip_path == "data/clips/clip-sin-url.mp4"


def test_alerta_conserva_clip_path(queue):
    """Verifica que clip_path se serializa y deserializa correctamente."""
    original = make_alert("clip-con-path")
    queue.push(original)

    recovered = queue.pop_all()[0]
    assert recovered.clip_path == original.clip_path