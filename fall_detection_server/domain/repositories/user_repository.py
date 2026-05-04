"""
Interfaz del repositorio de usuarios.
"""

from abc import abstractmethod
from typing import Optional

from domain.entities import User
from domain.repositories.base_repository import Repository


class UserRepository(Repository[User]):

    @abstractmethod
    async def find_by_email(self, email: str) -> Optional[User]:
        """Busca un usuario por su email."""
        ...