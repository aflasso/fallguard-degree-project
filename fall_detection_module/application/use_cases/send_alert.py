"""
Caso de uso: SendAlert
Orquesta el flujo completo desde un FallEvent confirmado hasta la alerta enviada:
  1. Inicia grabación del clip (ClipRecorder maneja contexto antes/después)
  2. Cuando el clip está listo, lo sube al bucket via ClipStorage
  3. Construye la Alert
  4. Intenta enviarla al servidor via AlertSender
  5. Si no hay conexión la guarda en AlertQueue (cola local)
"""

from typing import Optional
import uuid
import logging

from domain.entities import FallEvent, Alert
from application.ports.clip_storage import ClipStorage
from application.ports.alert_sender import AlertSender
from application.ports.alert_queue import AlertQueue
from application.ports.clip_recorder import ClipRecorder

logger = logging.getLogger(__name__)


class SendAlert:
    """
    Caso de uso que maneja el flujo completo de una alerta de caída.

    Depende de:
        - ClipRecorder : graba el clip con contexto antes/después (infraestructura)
        - ClipStorage  : sube el clip al bucket via presigned URL
        - AlertSender  : envía la alerta al servidor via WebSocket
        - AlertQueue   : cola local para alertas pendientes sin conexión
    """

    def __init__(
        self,
        clip_recorder: ClipRecorder,
        clip_storage:  ClipStorage,
        alert_sender:  Optional[AlertSender],
        alert_queue:   AlertQueue,
    ):
        self._clip_recorder = clip_recorder
        self._clip_storage  = clip_storage
        self._alert_sender  = alert_sender
        self._alert_queue   = alert_queue

    def execute(self, event: FallEvent) -> None:
        """
        Procesa un FallEvent iniciando la grabación del clip.
        El resto del flujo ocurre de forma diferida cuando el clip está listo
        a través del callback _on_clip_ready.

        Args:
            event: FallEvent confirmado por el dominio
        """
        if self._clip_recorder.is_recording():
            logger.warning(
                "Ya hay una grabación en curso — "
                "evento ignorado para evitar solapamiento"
            )
            return

        clip_id = str(uuid.uuid4())
        logger.info(f"Iniciando grabación de clip: {clip_id}")

        # El ClipRecorder llama a _on_clip_ready cuando el clip esté listo
        self._clip_recorder.record(
            event=event,
            on_ready=lambda clip_path: self._on_clip_ready(
                event, clip_id, clip_path
            ),
        )

    def set_alert_sender(self, sender: AlertSender) -> None:
        """Permite inyectar el AlertSender después de la construcción."""
        self._alert_sender = sender

    def _on_clip_ready(
        self,
        event:     FallEvent,
        clip_id:   str,
        clip_path: str,
    ) -> None:
        """
        Callback invocado por el ClipRecorder cuando el clip está grabado.
        Sube el clip y envía la alerta.
        """
        logger.info(f"Clip listo: {clip_path}")

        # Subir clip al bucket
        clip_url = None
        try:
            clip_url = self._clip_storage.upload(clip_path, clip_id)
            logger.info(f"Clip subido: {clip_url}")
        except Exception as e:
            logger.error(f"Error subiendo clip {clip_id}: {e}")

        # Construir alerta
        alert = Alert(
            module_id=  event.module_id,
            timestamp=  event.timestamp,
            confidence= event.confidence,
            clip_id=    clip_id,
            clip_path=  clip_path,
            clip_url=   clip_url,
            sent=       False,
        )

        # Intentar enviar al servidor
        self._dispatch(alert)

    def _dispatch(self, alert: Alert) -> None:
        """
        Envía la alerta al servidor o la guarda en cola local si no hay conexión.
        """
        if self._alert_sender.is_connected() and alert.clip_url is not None:
            sent = self._alert_sender.send(alert)
            if sent:
                logger.info(f"Alerta enviada: {alert.clip_id}")
                return

        # Sin conexión o fallo de envío → cola local
        self._alert_queue.push(alert)
        logger.warning(
            f"Alerta guardada en cola local: {alert.clip_id} "
            f"(pendientes: {self._alert_queue.size()})"
        )

    def flush_pending(self) -> int:
        """
        Intenta reenviar las alertas pendientes en la cola local.
        Si la alerta no tiene clip_url, intenta subir el clip local primero.
        Se llama cuando el WebSocket reconecta.

        Returns:
            Número de alertas enviadas exitosamente
        """
        if self._alert_queue.is_empty():
            return 0

        if not self._alert_sender.is_connected():
            logger.warning("flush_pending: sin conexión, no se pueden reenviar alertas")
            return 0

        pending = self._alert_queue.pop_all()
        sent_count = 0

        for alert in pending:

            # Sin clip_url ni clip_path — no hay nada que enviar
            if alert.clip_url is None and alert.clip_path is None:
                logger.warning(f"Alerta descartada sin clip: {alert.clip_id}")
                continue

            # Tiene clip local pero no fue subido — intentar subir ahora
            if alert.clip_url is None and alert.clip_path is not None:
                try:
                    clip_url = self._clip_storage.upload(alert.clip_path, alert.clip_id)
                    alert = Alert(
                        module_id=  alert.module_id,
                        timestamp=  alert.timestamp,
                        confidence= alert.confidence,
                        clip_id=    alert.clip_id,
                        clip_path=  alert.clip_path,
                        clip_url=   clip_url,
                        sent=       False,
                    )
                    logger.info(f"Clip pendiente subido: {clip_url}")
                except Exception as e:
                    logger.error(f"Error subiendo clip pendiente {alert.clip_id}: {e}")
                    self._alert_queue.push(alert)
                    continue

            # Enviar alerta al servidor
            if self._alert_sender.send(alert):
                sent_count += 1
                logger.info(f"Alerta pendiente enviada: {alert.clip_id}")
            else:
                self._alert_queue.push(alert)
                logger.warning(f"No se pudo reenviar alerta: {alert.clip_id}")

        logger.info(f"flush_pending: {sent_count}/{len(pending)} alertas enviadas")
        return sent_count