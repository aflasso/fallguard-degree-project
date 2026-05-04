"""
Puerto — cola de alertas pendientes.
Define qué necesita la aplicación para persistir alertas sin conexión.
La implementación concreta está en infrastructure/storage/local_queue.py
"""

from abc import ABC, abstractmethod
from typing import List

from domain.entities import Alert


class AlertQueue(ABC):

    @abstractmethod
    def push(self, alert: Alert) -> None:
        """Guarda una alerta pendiente en la cola."""
        ...

    @abstractmethod
    def pop_all(self) -> List[Alert]:
        """
        Retorna todas las alertas pendientes y las elimina de la cola.
        Se usa al reconectar para reenviar las alertas guardadas.
        """
        ...

    @abstractmethod
    def is_empty(self) -> bool:
        """True si no hay alertas pendientes."""
        ...

    @abstractmethod
    def size(self) -> int:
        """Número de alertas pendientes."""
        ...