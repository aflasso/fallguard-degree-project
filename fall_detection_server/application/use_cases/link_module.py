"""
Caso de uso: LinkModule
Vincula un módulo a un usuario cuando escanea el QR.
"""

import logging

from domain.repositories.module_repository import ModuleRepository
from domain.repositories.user_repository import UserRepository
from application.dtos.module_dtos import LinkModuleCommand

logger = logging.getLogger(__name__)


class LinkModule:

    def __init__(
        self,
        module_repository: ModuleRepository,
        user_repository:   UserRepository,
    ):
        self._module_repo = module_repository
        self._user_repo   = user_repository

    async def execute(self, command: LinkModuleCommand) -> None:
        """
        Vincula un módulo a un usuario.

        Raises:
            ValueError si el módulo o el usuario no existen
        """
        module = await self._module_repo.find_by_id(command.module_id)
        if module is None:
            raise ValueError(f"Módulo no encontrado: {command.module_id}")

        user = await self._user_repo.find_by_id(command.user_id)
        if user is None:
            raise ValueError(f"Usuario no encontrado: {command.user_id}")

        module.user_id = command.user_id
        await self._module_repo.save(module)

        logger.info(f"Módulo {command.module_id} vinculado a usuario {command.user_id}")