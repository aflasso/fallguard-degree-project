"""
Interfaz base genérica para todos los repositorios.
"""

from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional, List

T = TypeVar("T")


class Repository(ABC, Generic[T]):

    @abstractmethod
    async def save(self, entity: T) -> None:
        """Guarda o actualiza una entidad."""
        ...

    @abstractmethod
    async def find_by_id(self, id: str) -> Optional[T]:
        """Busca una entidad por su ID. Retorna None si no existe."""
        ...

    @abstractmethod
    async def find_all(self) -> List[T]:
        """Retorna todas las entidades."""
        ...

    @abstractmethod
    async def delete(self, id: str) -> None:
        """Elimina una entidad por su ID."""
        ...