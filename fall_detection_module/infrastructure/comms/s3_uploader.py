"""
Infraestructura — implementación de ClipStorage.
Implementa el puerto application/ports/clip_storage.py

Sube clips al bucket S3 usando presigned URLs.
El flujo es:
  1. Solicita presigned URL al servidor via HTTP
  2. Sube el clip directamente al bucket usando esa URL
  3. Retorna la URL pública del clip
"""

import logging
import os
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

    def __init__(
        self,
        server_url:  str,
        module_id:   str,
        timeout:     int = 30,
    ):
        self._server_url = server_url.rstrip("/")
        self._module_id  = module_id
        self._timeout    = timeout

    # ── Puerto ────────────────────────────────────────────────────────────

    def upload(self, clip_path: str, clip_id: str) -> str:
        """
        1. Solicita presigned URL al servidor
        2. Sube el clip directamente al bucket
        3. Retorna URL pública del clip

        Args:
            clip_path: ruta local del archivo .mp4
            clip_id:   UUID del clip

        Returns:
            URL pública del clip en el bucket

        Raises:
            FileNotFoundError: si el clip no existe en disco
            RuntimeError: si falla la solicitud de URL o la subida
        """
        if not Path(clip_path).exists():
            raise FileNotFoundError(f"Clip no encontrado: {clip_path}")

        # 1. Solicitar presigned URL al servidor
        presigned_url, public_url = self._request_upload_url(clip_id)

        # 2. Subir clip directamente al bucket
        self._upload_to_bucket(clip_path, presigned_url)

        logger.info(f"Clip subido correctamente: {public_url}")
        return public_url

    # ── Helpers ───────────────────────────────────────────────────────────

    def _request_upload_url(self, clip_id: str) -> tuple[str, str]:
        """
        Solicita al servidor una presigned URL para subir el clip.
        Retorna (presigned_url, public_url).
        """
        url = f"{self._server_url}/api/clips/upload-url"
        payload = {
            "module_id": self._module_id,
            "clip_id":   clip_id,
        }

        try:
            response = requests.post(url, json=payload, timeout=self._timeout)
            response.raise_for_status()
            data = response.json()
            return data["presigned_url"], data["public_url"]
        except requests.exceptions.Timeout:
            raise RuntimeError(f"Timeout solicitando presigned URL para {clip_id}")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Error solicitando presigned URL: {e}")

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