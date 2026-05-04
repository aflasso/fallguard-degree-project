"""
Caso de uso: HandleFallAlert
Se ejecuta cuando el servidor recibe una alerta de caída del módulo.
  1. Verifica que el módulo existe y está vinculado a un usuario
  2. Guarda la alerta en la BD
  3. Envía push notification al usuario
"""

import logging
import uuid
from datetime import datetime, timezone

from domain.entities import Alert
from domain.repositories.module_repository import ModuleRepository
from domain.repositories.alert_repository import AlertRepository
from domain.repositories.user_repository import UserRepository
from application.ports.notification_sender import NotificationSender
from application.dtos.alert_dtos import ProcessFallAlertCommand

logger = logging.getLogger(__name__)


class HandleFallAlert:

    def __init__(
        self,
        module_repository: ModuleRepository,
        alert_repository:  AlertRepository,
        user_repository:   UserRepository,
        notification_sender: NotificationSender,
    ):
        self._module_repo = module_repository
        self._alert_repo  = alert_repository
        self._user_repo   = user_repository
        self._notif       = notification_sender

    async def execute(self, command: ProcessFallAlertCommand) -> Alert:
        """
        Procesa una alerta de caída.

        Returns:
            Alert guardada en la BD
        """
        # Verificar que el módulo existe
        module = await self._module_repo.find_by_id(command.module_id)
        if module is None:
            raise ValueError(f"Módulo no encontrado: {command.module_id}")

        if module.user_id is None:
            logger.warning(f"Módulo sin usuario vinculado: {command.module_id}")
            raise ValueError(f"El modulo no ha sido vinculado {command.module_id}")

        # Crear y guardar la alerta
        alert = Alert(
            alert_id=   str(uuid.uuid4()),
            module_id=  command.module_id,
            timestamp=  command.timestamp,
            confidence= command.confidence,
            user_id=    module.user_id,
            clip_url=   command.clip_url,
            seen=       False,
        )
        await self._alert_repo.save(alert)
        logger.info(f"Alerta guardada: {alert.alert_id} | módulo={command.module_id}")

        # Enviar push notification si el módulo tiene usuario vinculado
        user = await self._user_repo.find_by_id(module.user_id)
        if user is not None and user.fcm_token is not None:
            await self._notif.send_fall_alert(user, alert)
            logger.info(f"Notificación enviada a usuario: {module.user_id}")
        else:
            logger.warning(f"Usuario sin FCM token: {module.user_id}")

        return alert