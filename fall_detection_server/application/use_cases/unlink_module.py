"""
Caso de uso: UnlinkModule
Desvincula un módulo de su usuario. El módulo debe detener la detección.
"""

import logging

from domain.repositories.module_repository import ModuleRepository
from application.ports.connection_manager import ConnectionManager
from application.dtos.module_dtos import UnlinkModuleCommand

logger = logging.getLogger(__name__)


class UnlinkModule:

    def __init__(
        self,
        module_repository:  ModuleRepository,
        connection_manager: ConnectionManager,
    ):
        self._module_repo        = module_repository
        self._connection_manager = connection_manager

    async def execute(self, command: UnlinkModuleCommand) -> None:
        """
        Desvincula un módulo de su usuario.

        Raises:
            ValueError si el módulo no existe
            PermissionError si el módulo pertenece a otro usuario
        """
        module = await self._module_repo.find_by_id(command.module_id)
        if module is None:
            raise ValueError(f"Módulo no encontrado: {command.module_id}")

        if module.user_id is not None and module.user_id != command.user_id:
            raise PermissionError("Módulo vinculado a otro usuario")

        module.user_id = None
        await self._module_repo.save(module)

        logger.info(f"Módulo {command.module_id} desvinculado de usuario {command.user_id}")

        # Avisar al módulo en caliente para que detenga la detección si está conectado
        await self._connection_manager.send(command.module_id, {"type": "module_unlinked"})
