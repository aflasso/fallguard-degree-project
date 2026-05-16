"""
Implementación del AlertRepository usando Firestore.
"""

import logging
from typing import List
from datetime import datetime
from google.cloud.firestore_v1 import AsyncClient

from domain.entities import Alert, AlertStatus
from domain.repositories.alert_repository import AlertRepository
from infrastructure.firestore.base_repository import FirestoreRepository

logger = logging.getLogger(__name__)


def _normalize_status(value: str) -> str:
    # "pending" was the old value for the initial state; map to "detected"
    return "detected" if value == "pending" else value


class FirestoreAlertRepository(FirestoreRepository[Alert], AlertRepository):

    def __init__(self, db: AsyncClient):
        super().__init__(db, collection_name="alerts", entity_class=Alert)

    # ── Métodos específicos ───────────────────────────────────────────────

    async def find_by_user(self, user_id: str) -> List[Alert]:
        docs = await self._collection \
            .where("user_id", "==", user_id) \
            .order_by("timestamp", direction="DESCENDING") \
            .get()
        return [self._from_dict(doc.to_dict()) for doc in docs]

    async def find_by_module(self, module_id: str) -> List[Alert]:
        docs = await self._collection \
            .where("module_id", "==", module_id) \
            .order_by("timestamp", direction="DESCENDING") \
            .get()
        return [self._from_dict(doc.to_dict()) for doc in docs]

    # ── Serialización ─────────────────────────────────────────────────────

    def _get_id(self, entity: Alert) -> str:
        return entity.alert_id

    def _to_dict(self, entity: Alert) -> dict:
        return {
            "alert_id":   entity.alert_id,
            "module_id":  entity.module_id,
            "user_id":    entity.user_id,
            "timestamp":  entity.timestamp,
            "confidence": entity.confidence,
            "clip_url":   entity.clip_url,
            "seen":       entity.seen,
            "status":     entity.status.value,
        }

    def _from_dict(self, data: dict) -> Alert:
        return Alert(
            alert_id=   data["alert_id"],
            module_id=  data["module_id"],
            user_id=    data.get("user_id"),
            timestamp=  data["timestamp"],
            confidence= data["confidence"],
            clip_url=   data.get("clip_url"),
            seen=       data.get("seen", False),
            status=     AlertStatus(_normalize_status(data.get("status", "detected"))),
        )