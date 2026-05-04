"""
Interfaz del repositorio de alertas.
"""

from abc import abstractmethod
from typing import List

from domain.entities import Alert
from domain.repositories.base_repository import Repository


class AlertRepository(Repository[Alert]):

    @abstractmethod
    async def find_by_user(self, user_id: str) -> List[Alert]:
        """Retorna todas las alertas de un usuario ordenadas por timestamp."""
        ...

    @abstractmethod
    async def find_by_module(self, module_id: str) -> List[Alert]:
        """Retorna todas las alertas de un módulo."""
        ...