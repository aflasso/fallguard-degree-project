"""
Interfaz del repositorio de módulos.
"""

from abc import abstractmethod
from typing import List, Optional

from domain.entities import Module
from domain.repositories.base_repository import Repository


class ModuleRepository(Repository[Module]):

    @abstractmethod
    async def find_by_user(self, user_id: str) -> List[Module]:
        """Retorna todos los módulos asociados a un usuario."""
        ...

    @abstractmethod
    async def find_all_connected(self) -> List[Module]:
        """Retorna todos los módulos conectados actualmente."""
        ...