"""
Configuración central del módulo de detección de caídas.
Todos los parámetros configurables del sistema en un solo lugar.
Lee desde variables de entorno con valores por defecto.
"""

import os
import uuid
from pathlib import Path
from dotenv import load_dotenv
from typing import Union

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

# Fuente de video — índice de cámara o ruta a video
CAMERA_SOURCE = os.getenv("CAMERA_SOURCE", "0")

def get_camera_source() -> Union[int, str]:
    """Retorna int si es índice de cámara, str si es ruta de video."""
    try:
        return int(CAMERA_SOURCE)
    except ValueError:
        return CAMERA_SOURCE


# ── Servidor ──────────────────────────────────────────────────────────────────
SERVER_WS_URL  = os.getenv("SERVER_WS_URL",  "ws://localhost:8000/ws")
SERVER_HTTP_URL = os.getenv("SERVER_HTTP_URL", "http://localhost:8000")


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