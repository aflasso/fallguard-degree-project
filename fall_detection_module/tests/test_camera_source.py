"""
Tests de la fuente de cámara dinámica:
  - prioridad de resolución (servidor > persistida > env > ninguna)
  - ActiveCamera: Thread 3 solicita, Thread 1 abre

Usa un .mp4 sintético: no depende del dataset, corre siempre.
"""

import cv2
import numpy as np
import pytest

import config
from infrastructure.video.active_camera import ActiveCamera


@pytest.fixture
def video(tmp_path):
    """Un .mp4 de 10 frames que OpenCV puede abrir."""
    path = tmp_path / "probe.mp4"
    w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 25.0, (64, 48))
    for _ in range(10):
        w.write(np.zeros((48, 64, 3), np.uint8))
    w.release()
    return str(path)


@pytest.fixture
def otro_video(tmp_path):
    path = tmp_path / "probe2.mp4"
    w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 25.0, (64, 48))
    for _ in range(10):
        w.write(np.full((48, 64, 3), 128, np.uint8))
    w.release()
    return str(path)


# ── Resolución de la fuente ───────────────────────────────────────────────────

def test_sin_fuente_ni_persistida_ni_env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CAMERA_SOURCE", "")
    monkeypatch.setattr(config, "CAMERA_SOURCE_PATH", str(tmp_path / "src.txt"))
    assert config.resolve_camera_source() is None


def test_env_se_usa_si_no_hay_persistida(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CAMERA_SOURCE", "http://camara/video")
    monkeypatch.setattr(config, "CAMERA_SOURCE_PATH", str(tmp_path / "src.txt"))
    assert config.resolve_camera_source() == "http://camara/video"


def test_persistida_le_gana_al_env(tmp_path, monkeypatch):
    """La fuente que eligió el usuario en la app manda sobre docker.env."""
    monkeypatch.setattr(config, "CAMERA_SOURCE", "http://vieja/video")
    monkeypatch.setattr(config, "CAMERA_SOURCE_PATH", str(tmp_path / "src.txt"))
    config.save_camera_source("http://elegida-en-la-app/video")
    assert config.resolve_camera_source() == "http://elegida-en-la-app/video"


def test_indice_de_camara_fisica_se_parsea_como_int(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CAMERA_SOURCE", "0")
    monkeypatch.setattr(config, "CAMERA_SOURCE_PATH", str(tmp_path / "src.txt"))
    assert config.resolve_camera_source() == 0


# ── ActiveCamera ──────────────────────────────────────────────────────────────

def test_arranca_sin_fuente():
    cam = ActiveCamera(None)
    assert not cam.has_source()
    assert not cam.needs_open()      # nada que abrir
    assert cam.instance is None


def test_solicitar_fuente_no_abre_nada(video):
    """request_source corre en Thread 3: solo marca. Abrir es de Thread 1."""
    cam = ActiveCamera(None)
    cam.request_source(video)

    assert cam.has_source()
    assert cam.instance is None      # todavía no abrió
    assert cam.needs_open()

    assert cam.open() is True        # Thread 1
    assert cam.instance is not None
    assert not cam.needs_open()
    cam.release()


def test_cambio_de_fuente_marca_reapertura(video, otro_video):
    cam = ActiveCamera(video)
    assert cam.open() is True
    assert not cam.needs_open()

    cam.request_source(otro_video)
    assert cam.needs_open()

    assert cam.open() is True
    assert cam.instance.source == otro_video
    cam.release()


def test_misma_fuente_no_dispara_reapertura(video):
    cam = ActiveCamera(video)
    cam.open()
    cam.request_source(video)
    assert not cam.needs_open()
    cam.release()


def test_fuente_invalida_no_revienta_y_permite_reintentar():
    """El módulo no muere si la cámara no abre: Thread 1 reintenta con backoff."""
    cam = ActiveCamera("/no/existe.mp4")
    assert cam.open() is False
    assert cam.instance is None
    assert cam.needs_open()          # sigue pendiente → se reintenta


def test_release_deja_el_contenedor_vacio(video):
    cam = ActiveCamera(video)
    cam.open()
    cam.release()
    assert cam.instance is None
