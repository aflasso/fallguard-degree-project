"""
Configuración central del módulo de detección de caídas.
Todos los parámetros configurables del sistema en un solo lugar.
Lee desde variables de entorno con valores por defecto.
"""

import os
import uuid
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional, Union

load_dotenv()

# ── Identidad del módulo ──────────────────────────────────────────────────────
# El MODULE_ID se genera una vez y se persiste en disco
# para que sea el mismo entre reinicios

def _load_or_create_module_id(id_file: str = "data/module_id.txt") -> str:
    path = Path(id_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return path.read_text().strip()
    module_id = str(uuid.uuid4())
    path.write_text(module_id)
    return module_id

MODULE_ID = _load_or_create_module_id()


# ── Estado de vinculación ─────────────────────────────────────────────────────
# Se persiste para sobrevivir reinicios estando offline. El servidor lo re-afirma
# al reconectar, así que si te desvincularon offline se corrige en la próxima conexión.
LINKED_STATE_PATH = os.getenv("LINKED_STATE_PATH", "data/linked_state.txt")

def load_linked_state() -> bool:
    path = Path(LINKED_STATE_PATH)
    if path.exists():
        return path.read_text().strip() == "1"
    return False

def save_linked_state(linked: bool) -> None:
    path = Path(LINKED_STATE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("1" if linked else "0")

# ── Fuente de video ───────────────────────────────────────────────────────────
# La fuente la elige el usuario desde la app y el servidor la empuja por
# WebSocket. `CAMERA_SOURCE` es solo un valor de arranque para pruebas: en el
# momento en que el módulo recibe una fuente del servidor deja de usarse.
#
# Prioridad: servidor (en vivo) > persistida en disco > CAMERA_SOURCE > sin fuente.
#
# Vacío significa "sin fuente": el módulo arranca y espera a que la app le
# configure una, igual que espera a estar vinculado.
CAMERA_SOURCE = os.getenv("CAMERA_SOURCE", "")

CAMERA_SOURCE_PATH = os.getenv("CAMERA_SOURCE_PATH", "data/camera_source.txt")


def _parse_source(raw: str) -> Optional[Union[int, str]]:
    """int si es índice de cámara física, str si es URL o ruta, None si está vacío."""
    raw = raw.strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return raw


def get_camera_source() -> Optional[Union[int, str]]:
    """Fuente configurada por entorno (valor de arranque)."""
    return _parse_source(CAMERA_SOURCE)


def load_camera_source() -> Optional[str]:
    """Última fuente enviada por el servidor, persistida en disco."""
    path = Path(CAMERA_SOURCE_PATH)
    if path.exists():
        return path.read_text(encoding="utf-8").strip() or None
    return None


def save_camera_source(url: str) -> None:
    path = Path(CAMERA_SOURCE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(url, encoding="utf-8")


def resolve_camera_source() -> Optional[Union[int, str]]:
    """
    Fuente con la que arrancar. La persistida gana sobre el entorno: es la que
    eligió el usuario en la app, y permite que un módulo ya configurado arranque
    aunque no haya conexión. El servidor la re-afirma al conectar.
    """
    persisted = load_camera_source()
    if persisted is not None:
        return _parse_source(persisted)
    return get_camera_source()


# Timeouts del backend FFmpeg para streams de red (cámara IP). Solo aplican a
# fuentes rtsp://, http://, etc. Sin ellos, una cámara congelada bloquea read()
# indefinidamente en vez de devolver None, y el módulo nunca reconecta.
CAMERA_OPEN_TIMEOUT_MS = int(os.getenv("CAMERA_OPEN_TIMEOUT_MS", "5000"))
CAMERA_READ_TIMEOUT_MS = int(os.getenv("CAMERA_READ_TIMEOUT_MS", "5000"))


# ── Servidor ──────────────────────────────────────────────────────────────────
SERVER_WS_URL   = os.getenv("SERVER_WS_URL",   "ws://localhost:8000/ws")
SERVER_HTTP_URL = os.getenv("SERVER_HTTP_URL", "http://localhost:8000")
MODULE_API_KEY  = os.getenv("MODULE_API_KEY",  "")


# ── Modelos ───────────────────────────────────────────────────────────────────
YOLO_MODEL_PATH = os.getenv("YOLO_MODEL_PATH", "models/yolo11x-pose.pt")
LSTM_MODEL_PATH = os.getenv("LSTM_MODEL_PATH", "models/fall_lstm_final.pt")
DEVICE          = os.getenv("DEVICE",          "cuda:0")


# ── Detección ─────────────────────────────────────────────────────────────────
CONF_YOLO      = float(os.getenv("CONF_YOLO",      "0.8"))   # confianza mínima YOLO
CONF_LSTM      = float(os.getenv("CONF_LSTM",      "0.7"))   # confianza mínima LSTM
MIN_FRAMES     = int(os.getenv("MIN_FRAMES",       "3"))      # frames consecutivos para confirmar
ALERT_COOLDOWN = int(os.getenv("ALERT_COOLDOWN",   "30"))     # frames de cooldown tras alerta


# ── Clip de video ─────────────────────────────────────────────────────────────
CLIPS_DIR       = os.getenv("CLIPS_DIR",        "data/clips")
CONTEXT_BEFORE  = int(os.getenv("CONTEXT_BEFORE",  "75"))    # ~3s a 25fps
CONTEXT_AFTER   = int(os.getenv("CONTEXT_AFTER",   "50"))    # ~2s a 25fps
VIDEO_FPS       = float(os.getenv("VIDEO_FPS",     "25.0"))


# ── Cola local ────────────────────────────────────────────────────────────────
LOCAL_QUEUE_PATH = os.getenv("LOCAL_QUEUE_PATH", "data/pending_alerts.json")


# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")