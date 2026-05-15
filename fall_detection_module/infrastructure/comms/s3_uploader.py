"""
Infraestructura — implementación de ClipStorage.
Implementa el puerto application/ports/clip_storage.py

Sube clips al bucket usando una presigned URL obtenida previamente via WebSocket.
El flujo es:
  1. Recibe presigned_url y public_url (obtenidas por WebSocketClient)
  2. Sube el clip directamente al bucket via PUT
  3. Retorna la URL pública del clip
"""

import logging
import requests
from pathlib import Path

from application.ports.clip_storage import ClipStorage

logger = logging.getLogger(__name__)


class S3ClipUploader(ClipStorage):
    """
    Implementa ClipStorage subiendo clips a S3 via presigned URLs.
    
    El servidor genera la presigned URL temporalmente — así las 
    credenciales de S3 nunca llegan al módulo local.
    """

    def __init__(self, timeout: int = 30):
        self._timeout = timeout

    # ── Puerto ────────────────────────────────────────────────────────────

    def upload(self, clip_path: str, presigned_url: str, public_url: str) -> str:
        """
        Sube el clip directamente al bucket usando la presigned URL provista
        y retorna la URL pública.

        Args:
            clip_path:     ruta local del archivo .mp4
            presigned_url: URL firmada para PUT directo al bucket (obtenida via WebSocket)
            public_url:    URL pública resultante

        Raises:
            FileNotFoundError: si el clip no existe en disco
            RuntimeError: si falla la subida
        """
        if not Path(clip_path).exists():
            raise FileNotFoundError(f"Clip no encontrado: {clip_path}")

        self._upload_to_bucket(clip_path, presigned_url)

        logger.info(f"Clip subido correctamente: {public_url}")
        return public_url

    # ── Helpers ───────────────────────────────────────────────────────────

    def _upload_to_bucket(self, clip_path: str, presigned_url: str) -> None:
        """
        Sube el clip directamente al bucket usando la presigned URL.
        """
        try:
            with open(clip_path, "rb") as f:
                response = requests.put(
                    presigned_url,
                    data=f,
                    headers={"Content-Type": "video/mp4"},
                    timeout=self._timeout,
                )
                response.raise_for_status()
        except requests.exceptions.Timeout:
            raise RuntimeError(f"Timeout subiendo clip a bucket: {clip_path}")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Error subiendo clip al bucket: {e}")
        except OSError as e:
            raise RuntimeError(f"Error leyendo clip: {e}")