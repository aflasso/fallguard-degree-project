"""
Puerto — generador de presigned URLs para subida de clips.
La implementación concreta está en infrastructure/s3/presigned_url.py
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class UploadUrlResult:
    presigned_url: str
    public_url:    str
    expires_in:    int   # segundos


class UploadUrlGenerator(ABC):

    @abstractmethod
    async def generate(self, clip_id: str, user_id: str, module_id: str) -> UploadUrlResult:
        """
        Genera una presigned URL para subir (PUT) un clip al bucket.
        Path resultante: clips/{user_id}/{module_id}/{clip_id}.mp4
        """
        ...

    @abstractmethod
    async def generate_read_url(self, blob_name: str) -> str:
        """
        Genera una presigned URL para leer (GET) un objeto del bucket.
        Expira en 15 minutos.

        Args:
            blob_name: path del objeto dentro del bucket (ej. clips/uid/mid/cid.mp4)
        Returns:
            URL firmada para GET directo desde el cliente
        """
        ...