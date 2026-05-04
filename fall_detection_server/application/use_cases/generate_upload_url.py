"""
Caso de uso: GenerateUploadUrl
Genera una presigned URL para que el módulo suba un clip al bucket S3.
"""

import logging

from domain.repositories.module_repository import ModuleRepository
from application.ports.upload_url_generator import UploadUrlGenerator, UploadUrlResult
from application.dtos.alert_dtos import GenerateUploadUrlCommand

logger = logging.getLogger(__name__)


class GenerateUploadUrl:

    def __init__(
        self,
        module_repository:    ModuleRepository,
        upload_url_generator: UploadUrlGenerator,
    ):
        self._module_repo = module_repository
        self._generator   = upload_url_generator

    async def execute(self, command: GenerateUploadUrlCommand) -> UploadUrlResult:
        """
        Genera una presigned URL para subir un clip.

        Raises:
            ValueError si el módulo no existe
        """
        module = await self._module_repo.find_by_id(command.module_id)
        if module is None:
            raise ValueError(f"Módulo no encontrado: {command.module_id}")

        result = await self._generator.generate(command.clip_id)
        logger.info(f"Presigned URL generada para clip: {command.clip_id}")
        return result