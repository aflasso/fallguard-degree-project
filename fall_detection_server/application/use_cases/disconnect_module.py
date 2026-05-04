"""
Caso de uso: DisconnectModule
Se ejecuta cuando un módulo se desconecta del servidor.
Actualiza su estado en Firestore a DISCONNECTED.
"""

import logging
from datetime import datetime, timezone

from domain.entities import ModuleStatus
from domain.repositories.module_repository import ModuleRepository

logger = logging.getLogger(__name__)


class DisconnectModule:

    def __init__(self, module_repository: ModuleRepository):
        self._module_repo = module_repository

    async def execute(self, module_id: str) -> None:
        """
        Marca el módulo como desconectado en Firestore.
        """
        module = await self._module_repo.find_by_id(module_id)
        if module is None:
            logger.warning(f"Módulo no encontrado al desconectar: {module_id}")
            return

        module.status    = ModuleStatus.DISCONNECTED
        module.last_seen = datetime.now(timezone.utc)
        await self._module_repo.save(module)
        logger.info(f"Módulo desconectado: {module_id}")