"""
Puerto — envío de push notifications.
La implementación concreta está en infrastructure/firebase/fcm_sender.py
"""

from abc import ABC, abstractmethod
from domain.entities import User, Alert


class NotificationSender(ABC):

    @abstractmethod
    async def send_fall_alert(self, user: User, alert: Alert) -> None:
        """
        Envía una push notification al usuario avisando de una caída.
        """
        ...

    @abstractmethod
    async def send_module_disconnected(self, user: User, module_id: str) -> None:
        """
        Envía una push notification al usuario avisando que su módulo se desconectó.
        """
        ...