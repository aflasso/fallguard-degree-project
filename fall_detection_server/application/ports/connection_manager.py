"""
Puerto — gestor de conexiones WebSocket activas.
Define cómo el servidor envía mensajes a módulos conectados.
La implementación concreta está en infrastructure/websocket/connection_manager.py
"""

from abc import ABC, abstractmethod
from typing import Optional


class ConnectionManager(ABC):

    @abstractmethod
    async def send(self, module_id: str, message: dict) -> bool:
        """
        Envía un mensaje a un módulo conectado.

        Args:
            module_id: ID del módulo destino
            message:   mensaje a enviar como dict (se serializa a JSON)

        Returns:
            True si se envió correctamente, False si el módulo no está conectado
        """
        ...

    @abstractmethod
    def is_connected(self, module_id: str) -> bool:
        """Retorna True si el módulo está conectado actualmente."""
        ...

    @abstractmethod
    def get_connected_modules(self) -> list:
        """Retorna lista de module_ids conectados actualmente."""
        ...