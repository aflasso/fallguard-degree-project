"""
Puerto — almacenamiento de clips.
Define qué necesita la aplicación para subir un clip al bucket.
La implementación concreta (S3 + presigned URL) está en infrastructure/comms/s3_uploader.py
"""

from abc import ABC, abstractmethod


class ClipStorage(ABC):

    @abstractmethod
    def upload(self, clip_path: str, presigned_url: str, public_url: str) -> str:
        """
        Sube el clip al bucket usando una presigned URL ya obtenida y retorna la URL pública.

        Args:
            clip_path:     ruta local del archivo de video
            presigned_url: URL firmada para PUT directo al bucket
            public_url:    URL pública resultante del clip

        Returns:
            URL pública del clip en el bucket
        """
        ...