"""
Caso de uso: SetCameraSource
Se ejecuta cuando el usuario configura o cambia la cámara de un módulo desde
la app (REST `PATCH /api/modules/{module_id}/camera`).

Persiste la URL y la empuja al módulo si está conectado. Si no lo está, el
módulo la recibirá al reconectar: `ConnectModule` la reenvía en ese momento.
"""

import logging

from domain.entities import Module
from domain.camera_source import validate_camera_url
from domain.repositories.module_repository import ModuleRepository
from application.ports.connection_manager import ConnectionManager
from application.dtos.module_dtos import SetCameraSourceCommand

logger = logging.getLogger(__name__)


class SetCameraSource:

    def __init__(
        self,
        module_repository:  ModuleRepository,
        connection_manager: ConnectionManager,
    ):
        self._module_repo        = module_repository
        self._connection_manager = connection_manager

    async def execute(self, command: SetCameraSourceCommand) -> Module:
        """
        Raises:
            LookupError     si el módulo no existe
            PermissionError si el módulo no está vinculado o pertenece a otro usuario
            ValueError      si la URL es inválida
        """
        module = await self._module_repo.find_by_id(command.module_id)
        if module is None:
            raise LookupError(f"Módulo no encontrado: {command.module_id}")

        if module.user_id is None:
            raise PermissionError("Módulo no vinculado a ningún usuario")
        if module.user_id != command.user_id:
            raise PermissionError("Módulo vinculado a otro usuario")

        # El módulo pasa esta cadena a cv2.VideoCapture — ver domain/camera_source.py
        url = validate_camera_url(command.url)

        module.camera_url = url

        # La cámara nueva todavía no reportó nada. Asumirla sana evita mostrar
        # "sin señal" heredado de la cámara anterior; el módulo corrige en
        # segundos con su camera_status real.
        module.camera_ok            = True
        module.camera_status_reason = None

        await self._module_repo.save(module)

        sent = await self._connection_manager.send(command.module_id, {
            "type": "set_camera_source",
            "url":  url,
        })

        if sent:
            logger.info(f"Fuente de cámara enviada a {command.module_id}")
        else:
            logger.info(
                f"Fuente de cámara guardada para {command.module_id} "
                f"— módulo desconectado, la recibirá al reconectar"
            )

        return module
