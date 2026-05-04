"""
Gestor de conexiones WebSocket activas.
Mantiene un registro de los módulos conectados y permite
enviarles mensajes directamente.
"""

import json
import logging
from typing import Dict, List
from fastapi import WebSocket

from application.ports.connection_manager import ConnectionManager

logger = logging.getLogger(__name__)


class WebSocketConnectionManager(ConnectionManager):
    """
    Mantiene un diccionario de conexiones WebSocket activas.
    module_id → WebSocket
    """

    def __init__(self):
        self._connections: Dict[str, WebSocket] = {}

    async def connect(self, module_id: str, websocket: WebSocket) -> None:
        """Registra una nueva conexión WebSocket."""
        self._connections[module_id] = websocket
        logger.info(f"Módulo conectado: {module_id} | activos={len(self._connections)}")

    async def disconnect(self, module_id: str) -> None:
        """Elimina una conexión WebSocket."""
        if module_id in self._connections:
            del self._connections[module_id]
            logger.info(f"Módulo desconectado: {module_id} | activos={len(self._connections)}")

    async def send(self, module_id: str, message: dict) -> bool:
        """
        Envía un mensaje a un módulo conectado.
        Retorna True si se envió correctamente, False si no está conectado.
        """
        websocket = self._connections.get(module_id)
        if websocket is None:
            logger.warning(f"Módulo no conectado: {module_id}")
            return False

        try:
            await websocket.send_text(json.dumps(message))
            return True
        except Exception as e:
            logger.error(f"Error enviando mensaje a {module_id}: {e}")
            await self.disconnect(module_id)
            return False

    def is_connected(self, module_id: str) -> bool:
        return module_id in self._connections

    def get_connected_modules(self) -> List[str]:
        return list(self._connections.keys())