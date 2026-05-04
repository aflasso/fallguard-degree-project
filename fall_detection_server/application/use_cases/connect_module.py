"""
Caso de uso: ConnectModule
Se ejecuta cuando un módulo se conecta al servidor via WebSocket.
  1. Busca el módulo en la BD — si no existe lo crea
  2. Actualiza su estado a CONNECTED y sus cámaras
  3. Retorna la configuración activa del módulo
"""

import logging
from datetime import datetime, timezone

from domain.entities import Module, ModuleStatus
from domain.repositories.module_repository import ModuleRepository
from application.dtos.module_dtos import ConnectModuleCommand, CameraInfoDTO
from domain.entities import CameraInfo

logger = logging.getLogger(__name__)


class ConnectModule:

    def __init__(self, module_repository: ModuleRepository):
        self._module_repo = module_repository

    async def execute(self, command: ConnectModuleCommand) -> Module:
        """
        Conecta un módulo al servidor.
        Si no existe lo registra automáticamente.

        Returns:
            Module actualizado con estado CONNECTED
        """
        module = await self._module_repo.find_by_id(command.module_id)

        if module is None:
            # Auto-registro — módulo nuevo
            module = Module(
                module_id= command.module_id,
                status=    ModuleStatus.CONNECTED,
                last_seen= datetime.now(timezone.utc),
                cameras=   [CameraInfo(id=c.id, name=c.name) for c in command.cameras],
            )
            logger.info(f"Módulo nuevo registrado: {command.module_id}")
        else:
            # Módulo existente — actualizar estado
            module.status    = ModuleStatus.CONNECTED
            module.last_seen = datetime.now(timezone.utc)
            module.cameras   = [CameraInfo(id=c.id, name=c.name) for c in command.cameras]
            logger.info(f"Módulo reconectado: {command.module_id}")

        await self._module_repo.save(module)
        return module