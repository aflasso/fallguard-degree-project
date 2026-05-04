"""
Puerto — almacenamiento de clips.
Define qué necesita la aplicación para subir un clip al bucket.
La implementación concreta (S3 + presigned URL) está en infrastructure/comms/s3_uploader.py
"""

from abc import ABC, abstractmethod


class ClipStorage(ABC):

    @abstractmethod
    def upload(self, clip_path: str, clip_id: str) -> str:
        """
        Sube el clip al bucket y retorna la URL pública.

        Args:
            clip_path: ruta local del archivo de video
            clip_id:   identificador único del clip (usado como nombre en el bucket)

        Returns:
            URL pública del clip en el bucket
        """
        ...