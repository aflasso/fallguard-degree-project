"""
Configuración central del servidor.
Lee desde variables de entorno con valores por defecto.
"""

import os
from dotenv import load_dotenv

load_dotenv()


# ── Firebase ──────────────────────────────────────────────────────────────────
FIREBASE_CREDENTIALS_PATH = os.getenv(
    "FIREBASE_CREDENTIALS_PATH",
    "credentials/serviceAccountKey.json"
)

# ── Google Cloud Storage ──────────────────────────────────────────────────────
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "fall-detection-clips")

# ── Servidor ──────────────────────────────────────────────────────────────────
HOST      = os.getenv("HOST",      "0.0.0.0")
PORT      = int(os.getenv("PORT",  "8000"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ── Heartbeat ─────────────────────────────────────────────────────────────────
HEARTBEAT_TIMEOUT = int(os.getenv("HEARTBEAT_TIMEOUT", "90"))  # segundos

# ── WebSocket ─────────────────────────────────────────────────────────────────
MODULE_API_KEY = os.getenv("MODULE_API_KEY", "")