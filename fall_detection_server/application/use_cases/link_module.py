"""
Caso de uso: LinkModule
Vincula un módulo a un usuario cuando escanea el QR.
"""

import logging

from domain.repositories.module_repository import ModuleRepository
from domain.repositories.user_repository import UserRepository
from application.ports.connection_manager import ConnectionManager
from application.dtos.module_dtos import LinkModuleCommand

logger = logging.getLogger(__name__)


class LinkModule:

    def __init__(
        self,
        module_repository:  ModuleRepository,
        user_repository:    UserRepository,
        connection_manager: ConnectionManager,
    ):
        self._module_repo        = module_repository
        self._user_repo          = user_repository
        self._connection_manager = connection_manager

    async def execute(self, command: LinkModuleCommand) -> None:
        """
        Vincula un módulo a un usuario.

        Raises:
            ValueError si el módulo o el usuario no existen
        """
        module = await self._module_repo.find_by_id(command.module_id)
        if module is None:
            raise ValueError(f"Módulo no encontrado: {command.module_id}")

        if module.user_id is not None and module.user_id != command.user_id:
            raise PermissionError(f"Módulo ya vinculado a otro usuario")

        user = await self._user_repo.find_by_id(command.user_id)
        if user is None:
            raise ValueError(f"Usuario no encontrado: {command.user_id}")

        module.user_id = command.user_id
        await self._module_repo.save(module)

        logger.info(f"Módulo {command.module_id} vinculado a usuario {command.user_id}")

        # Avisar al módulo en caliente para que arranque la detección si está conectado
        await self._connection_manager.send(command.module_id, {"type": "module_linked"})