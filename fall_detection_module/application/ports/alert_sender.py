"""
Puerto — envío de alertas.
Define qué necesita la aplicación para enviar una alerta al servidor.
La implementación concreta (WebSocket) está en infrastructure/comms/ws_client.py
"""

from abc import ABC, abstractmethod

from domain.entities import Alert


class AlertSender(ABC):

    @abstractmethod
    def send(self, alert: Alert) -> bool:
        """
        Envía una alerta al servidor central.

        Args:
            alert: alerta con clip_url ya disponible

        Returns:
            True si se envió correctamente, False si no hay conexión
        """
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        """Retorna True si hay conexión activa con el servidor."""
        ...