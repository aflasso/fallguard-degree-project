"""
Clase base para repositorios de Firestore.
Implementa los métodos comunes de Repository usando el SDK de Firebase Admin.
"""

import logging
from typing import TypeVar, Generic, Optional, List, Type
from google.cloud.firestore_v1 import AsyncClient

logger = logging.getLogger(__name__)

T = TypeVar("T")


class FirestoreRepository(Generic[T]):

    def __init__(self, db: AsyncClient, collection_name: str, entity_class: Type[T]):
        self._db              = db
        self._collection      = db.collection(collection_name)
        self._entity_class    = entity_class

    async def save(self, entity: T) -> None:
        """Guarda o actualiza una entidad en Firestore."""
        doc_id = self._get_id(entity)
        data   = self._to_dict(entity)
        await self._collection.document(doc_id).set(data)
        logger.debug(f"Guardado en {self._collection.id}: {doc_id}")

    async def find_by_id(self, id: str) -> Optional[T]:
        """Busca una entidad por su ID."""
        doc = await self._collection.document(id).get()
        if not doc.exists:
            return None
        return self._from_dict(doc.to_dict())

    async def find_all(self) -> List[T]:
        """Retorna todas las entidades de la colección."""
        docs = await self._collection.get()
        return [self._from_dict(doc.to_dict()) for doc in docs]

    async def delete(self, id: str) -> None:
        """Elimina una entidad por su ID."""
        await self._collection.document(id).delete()
        logger.debug(f"Eliminado de {self._collection.id}: {id}")

    # ── Métodos a implementar por subclases ───────────────────────────────

    def _get_id(self, entity: T) -> str:
        """Retorna el ID de la entidad — cada subclase define cuál campo es el ID."""
        raise NotImplementedError

    def _to_dict(self, entity: T) -> dict:
        """Convierte la entidad a dict para guardar en Firestore."""
        raise NotImplementedError

    def _from_dict(self, data: dict) -> T:
        """Reconstruye la entidad desde un dict de Firestore."""
        raise NotImplementedError