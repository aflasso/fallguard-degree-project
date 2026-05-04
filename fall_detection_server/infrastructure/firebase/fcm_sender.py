"""
Implementación de NotificationSender usando Firebase Cloud Messaging.
"""

import logging
from firebase_admin import messaging

from domain.entities import User, Alert
from application.ports.notification_sender import NotificationSender

logger = logging.getLogger(__name__)


class FCMNotificationSender(NotificationSender):

    async def send_fall_alert(self, user: User, alert: Alert) -> None:
        """Envía push notification de caída al usuario."""
        if not user.fcm_token:
            logger.warning(f"Usuario {user.user_id} sin FCM token")
            return

        message = messaging.Message(
            token= user.fcm_token,
            data= {
                "type":      "fall_detected",
                "alert_id":  alert.alert_id,
                "timestamp": alert.timestamp.isoformat(),
                "clip_url":  alert.clip_url or "",
                "title":     "Caída detectada",
                "body":      "Se detectó una caída en tu hogar",
            },
        )

        try:
            response = messaging.send(message)
            logger.info(f"Notificación enviada: {response}")
        except Exception as e:
            logger.error(f"Error enviando notificación a {user.user_id}: {e}")

    async def send_module_disconnected(self, user: User, module_id: str) -> None:
        """Envía push notification de módulo desconectado."""
        if not user.fcm_token:
            return

        message = messaging.Message(
            token= user.fcm_token,
            notification= messaging.Notification(
                title= "Módulo desconectado",
                body=  "No se ha podido contactar tu dispositivo de detección",
            ),
            data= {
                "module_id": module_id,
            },
        )

        try:
            response = messaging.send(message)
            logger.info(f"Notificación desconexión enviada: {response}")
        except Exception as e:
            logger.error(f"Error enviando notificación desconexión: {e}")