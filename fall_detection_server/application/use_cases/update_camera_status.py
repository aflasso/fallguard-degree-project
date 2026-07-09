"""
Caso de uso: UpdateCameraStatus
Se ejecuta cuando un módulo reporta que su cámara dejó de entregar frames
o que volvió a entregarlos (WebSocket `camera_status`).

Un módulo puede estar CONNECTED y ciego al mismo tiempo: el WebSocket sigue
vivo y el heartbeat llega, pero la cámara IP se cortó. Persistir este estado
es lo que permite que la app lo muestre en vez de dar el módulo por sano.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from domain.entities import Module
from domain.repositories.module_repository import ModuleRepository
from application.dtos.module_dtos import UpdateCameraStatusCommand

logger = logging.getLogger(__name__)


class UpdateCameraStatus:

    def __init__(self, module_repository: ModuleRepository):
        self._module_repo = module_repository

    async def execute(self, command: UpdateCameraStatusCommand) -> Optional[Module]:
        """
        Persiste el estado de cámara reportado por el módulo.

        Returns:
            Module actualizado, o None si el módulo no existe.
        """
        module = await self._module_repo.find_by_id(command.module_id)

        if module is None:
            logger.warning(f"camera_status de módulo desconocido: {command.module_id}")
            return None

        # El módulo re-afirma su estado en cada reconexión, así que la mayoría de
        # los reportes no son transiciones. Escribir igual mantendría vivo un
        # listener de Firestore en la app por nada.
        if module.camera_ok == command.camera_ok:
            return module

        module.camera_ok            = command.camera_ok
        module.camera_status_at     = datetime.now(timezone.utc)
        module.camera_status_reason = command.reason or None

        await self._module_repo.save(module)

        if command.camera_ok:
            logger.info(f"Cámara recuperada: {command.module_id}")
        else:
            logger.warning(
                f"Cámara caída: {command.module_id} — {command.reason or 'sin detalle'}"
            )

        return module
