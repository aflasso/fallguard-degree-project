"""
Implementación del ModuleRepository usando Firestore.
"""

import logging
from typing import List, Optional
from datetime import datetime, timezone
from google.cloud.firestore_v1 import AsyncClient

from domain.entities import Module, ModuleStatus, CameraInfo
from domain.repositories.module_repository import ModuleRepository
from infrastructure.firestore.base_repository import FirestoreRepository

logger = logging.getLogger(__name__)


class FirestoreModuleRepository(FirestoreRepository[Module], ModuleRepository):

    def __init__(self, db: AsyncClient):
        super().__init__(db, collection_name="modules", entity_class=Module)

    # ── Métodos específicos ───────────────────────────────────────────────

    async def find_by_user(self, user_id: str) -> List[Module]:
        docs = await self._collection.where("user_id", "==", user_id).get()
        return [self._from_dict(doc.to_dict()) for doc in docs]

    async def find_all_connected(self) -> List[Module]:
        docs = await self._collection.where("status", "==", ModuleStatus.CONNECTED.value).get()
        return [self._from_dict(doc.to_dict()) for doc in docs]

    # ── Serialización ─────────────────────────────────────────────────────

    def _get_id(self, entity: Module) -> str:
        return entity.module_id

    def _to_dict(self, entity: Module) -> dict:
        return {
            "module_id":            entity.module_id,
            "status":               entity.status.value,
            "last_seen":            entity.last_seen,
            "user_id":              entity.user_id,
            "cameras":              [{"id": c.id, "name": c.name} for c in entity.cameras],
            "display_name":         entity.display_name,
            "camera_ok":            entity.camera_ok,
            "camera_status_at":     entity.camera_status_at,
            "camera_status_reason": entity.camera_status_reason,
            "camera_url":           entity.camera_url,
        }

    def _from_dict(self, data: dict) -> Module:
        return Module(
            module_id=    data["module_id"],
            status=       ModuleStatus(data["status"]),
            last_seen=    data.get("last_seen"),
            # Normaliza "" / valores falsy a None — un módulo solo está vinculado
            # si tiene un user_id real. Esto mantiene consistente el chequeo
            # `user_id is None` en todo el servidor (link, upload, connected).
            user_id=      data.get("user_id") or None,
            cameras=      [CameraInfo(id=c["id"], name=c["name"]) for c in data.get("cameras", [])],
            display_name= data.get("display_name"),
            # Documentos anteriores a este campo no lo tienen: se asumen sanos.
            # El módulo re-afirma su estado real al conectarse.
            camera_ok=            data.get("camera_ok", True),
            camera_status_at=     data.get("camera_status_at"),
            camera_status_reason= data.get("camera_status_reason"),
            camera_url=           data.get("camera_url") or None,
        )