"""
Implementación del UserRepository usando Firestore.
"""

import logging
from typing import Optional
from google.cloud.firestore_v1 import AsyncClient

from domain.entities import User
from domain.repositories.user_repository import UserRepository
from infrastructure.firestore.base_repository import FirestoreRepository

logger = logging.getLogger(__name__)


class FirestoreUserRepository(FirestoreRepository[User], UserRepository):

    def __init__(self, db: AsyncClient):
        super().__init__(db, collection_name="users", entity_class=User)

    # ── Métodos específicos ───────────────────────────────────────────────

    async def find_by_email(self, email: str) -> Optional[User]:
        docs = await self._collection.where("email", "==", email).limit(1).get()
        if not docs:
            return None
        return self._from_dict(docs[0].to_dict())

    # ── Serialización ─────────────────────────────────────────────────────

    def _get_id(self, entity: User) -> str:
        return entity.user_id

    def _to_dict(self, entity: User) -> dict:
        return {
            "user_id":   entity.user_id,
            "email":     entity.email,
            "fcm_token": entity.fcm_token,
        }

    def _from_dict(self, data: dict) -> User:
        return User(
            user_id=   data["user_id"],
            email=     data["email"],
            fcm_token= data.get("fcm_token"),
        )