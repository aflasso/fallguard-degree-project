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
        Genera una presigned URL para subir un clip al bucket.

        Args:
            clip_id:   identificador único del clip
            user_id:   uid del usuario dueño del clip
            module_id: id del módulo que genera el clip
            Path resultante: clips/{user_id}/{module_id}/{clip_id}.mp4

        Returns:
            UploadUrlResult con presigned_url, public_url y expires_in
        """
        ...