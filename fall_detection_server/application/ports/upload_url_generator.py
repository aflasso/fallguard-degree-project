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
    async def generate(self, clip_id: str) -> UploadUrlResult:
        """
        Genera una presigned URL para subir un clip al bucket S3.

        Args:
            clip_id: identificador único del clip

        Returns:
            UploadUrlResult con presigned_url, public_url y expires_in
        """
        ...