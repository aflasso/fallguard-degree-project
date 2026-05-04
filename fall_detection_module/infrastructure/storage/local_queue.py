"""
Infraestructura — implementación de AlertQueue.
Implementa el puerto application/ports/alert_queue.py

Cola local persistida en disco como archivo JSON.
Guarda alertas pendientes cuando no hay conexión con el servidor.
Se vacía cuando el WebSocket reconecta y reenvía las alertas.
"""

import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import List
from pathlib import Path

from domain.entities import Alert
from application.ports.alert_queue import AlertQueue

logger = logging.getLogger(__name__)


class LocalAlertQueue(AlertQueue):
    """
    Implementa AlertQueue persistiendo las alertas en un archivo JSON.
    Thread-safe — usa Lock para proteger lecturas y escrituras concurrentes
    entre Thread 1 (detección) y Thread 3 (WebSocket).
    """

    def __init__(self, queue_path: str = "data/pending_alerts.json"):
        self._queue_path = Path(queue_path)
        self._lock       = threading.Lock()
        self._queue_path.parent.mkdir(parents=True, exist_ok=True)

        if not self._queue_path.exists():
            self._write([])

        logger.info(f"LocalAlertQueue iniciada | path={queue_path} | pendientes={self.size()}")

    # ── Puerto ────────────────────────────────────────────────────────────

    def push(self, alert: Alert) -> None:
        """Agrega una alerta a la cola y persiste en disco."""
        with self._lock:
            alerts = self._read()
            alerts.append(self._to_dict(alert))
            self._write(alerts)
            logger.info(f"Alerta guardada en cola local: {alert.clip_id} (total: {len(alerts)})")

    def pop_all(self) -> List[Alert]:
        """Retorna todas las alertas pendientes y vacía la cola."""
        with self._lock:
            alerts = self._read()
            if not alerts:
                return []
            self._write([])
            logger.info(f"Cola local vaciada: {len(alerts)} alertas recuperadas")
            return [self._from_dict(a) for a in alerts]

    def is_empty(self) -> bool:
        with self._lock:
            return len(self._read()) == 0

    def size(self) -> int:
        with self._lock:
            return len(self._read())

    # ── Helpers ───────────────────────────────────────────────────────────

    def _read(self) -> list:
        try:
            with open(self._queue_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _write(self, alerts: list) -> None:
        with open(self._queue_path, "w", encoding="utf-8") as f:
            json.dump(alerts, f, indent=2, ensure_ascii=False)

    def _to_dict(self, alert: Alert) -> dict:
        return {
            "module_id":  alert.module_id,
            "timestamp":  alert.timestamp.isoformat(),
            "confidence": alert.confidence,
            "clip_id":    alert.clip_id,
            "clip_path":  alert.clip_path,
            "clip_url":   alert.clip_url,
            "sent":       alert.sent,
        }

    def _from_dict(self, data: dict) -> Alert:
        return Alert(
            module_id=  data["module_id"],
            timestamp=  datetime.fromisoformat(data["timestamp"]),
            confidence= data["confidence"],
            clip_id=    data["clip_id"],
            clip_path=  data["clip_path"],
            clip_url=   data.get("clip_url"),
            sent=       data.get("sent", False),
        )