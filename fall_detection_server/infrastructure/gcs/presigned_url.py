"""
Implementación de UploadUrlGenerator usando Google Cloud Storage.
Usa las mismas credenciales del serviceAccountKey.json de Firebase.
"""

import logging
import datetime
from google.cloud import storage
from google.oauth2 import service_account

from application.ports.upload_url_generator import UploadUrlGenerator, UploadUrlResult
import config

logger = logging.getLogger(__name__)


class GCSPresignedUrlGenerator(UploadUrlGenerator):

    def __init__(self):
        # Usa las mismas credenciales del serviceAccountKey.json
        credentials = service_account.Credentials.from_service_account_file(
            config.FIREBASE_CREDENTIALS_PATH,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        self._client     = storage.Client(credentials=credentials)
        self._bucket     = self._client.bucket(config.GCS_BUCKET_NAME)
        self._expires_in = 300   # 5 minutos

    async def generate(self, clip_id: str, user_id: str, module_id: str) -> UploadUrlResult:
        """
        Genera una presigned URL para subir un clip a GCS.
        La clave del objeto será: clips/{user_id}/{module_id}/{clip_id}.mp4
        """
        blob_name = f"clips/{user_id}/{module_id}/{clip_id}.mp4"
        blob      = self._bucket.blob(blob_name)

        try:
            presigned_url = blob.generate_signed_url(
                version=       "v4",
                expiration=    datetime.timedelta(seconds=self._expires_in),
                method=        "PUT",
                content_type=  "video/mp4",
            )

            public_url = (
                f"https://storage.googleapis.com/"
                f"{config.GCS_BUCKET_NAME}/{blob_name}"
            )

            logger.info(f"Presigned URL generada para: {blob_name}")

            return UploadUrlResult(
                presigned_url= presigned_url,
                public_url=    public_url,
                expires_in=    self._expires_in,
            )

        except Exception as e:
            logger.error(f"Error generando presigned URL: {e}")
            raise RuntimeError(f"No se pudo generar presigned URL: {e}")