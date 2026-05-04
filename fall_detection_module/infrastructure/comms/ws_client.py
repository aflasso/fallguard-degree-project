"""
Infraestructura — cliente WebSocket.
Implementa el puerto application/ports/alert_sender.py

Responsabilidades:
  - Mantener conexión WebSocket con el servidor
  - Enviar alertas de caída
  - Enviar heartbeat cada 30s
  - Recibir mensajes del servidor (config_update, set_camera)
  - Reconexión automática con backoff exponencial
"""

import json
import logging
import threading
import time
from typing import Callable, Optional

import websocket

from domain.entities import Alert
from application.ports.alert_sender import AlertSender

logger = logging.getLogger(__name__)


class WebSocketClient(AlertSender):
    """
    Implementa AlertSender usando WebSocket.
    Corre en Thread 3 — mantiene la conexión y procesa mensajes.
    """

    HEARTBEAT_INTERVAL = 30   # segundos
    MAX_BACKOFF        = 60   # segundos máximo entre reintentos

    def __init__(
        self,
        server_url:  str,
        module_id:   str,
        cameras:     list,
        on_set_camera:     Optional[Callable[[int], None]]  = None,
        on_config_update:  Optional[Callable[[dict], None]] = None,
    ):
        self._server_url       = server_url
        self._module_id        = module_id
        self._cameras          = cameras
        self._on_set_camera    = on_set_camera
        self._on_config_update = on_config_update

        self._ws:          Optional[websocket.WebSocketApp] = None
        self._connected:   bool      = False
        self._lock         = threading.Lock()
        self._backoff:     float     = 1.0
        self._stop_event   = threading.Event()

    # ── Puerto ────────────────────────────────────────────────────────────

    def send(self, alert: Alert) -> bool:
        """
        Envía una alerta de caída al servidor.
        Retorna True si se envió correctamente, False si no hay conexión.
        """
        if not self._connected or self._ws is None:
            return False

        message = {
            "type":       "fall_alert",
            "module_id":  alert.module_id,
            "timestamp":  alert.timestamp.isoformat(),
            "confidence": alert.confidence,
            "clip_id":    alert.clip_id,
            "clip_url":   alert.clip_url,
        }

        try:
            self._ws.send(json.dumps(message))
            logger.info(f"Alerta enviada: {alert.clip_id}")
            return True
        except Exception as e:
            logger.error(f"Error enviando alerta: {e}")
            self._connected = False
            return False

    def is_connected(self) -> bool:
        return self._connected

    # ── Conexión ──────────────────────────────────────────────────────────

    def run(self, on_reconnect: Optional[Callable] = None) -> None:
        """
        Corre el cliente WebSocket con reconexión automática.
        Debe llamarse en Thread 3.

        Args:
            on_reconnect: callback que se llama cuando reconecta
                          usado para vaciar la cola local de alertas
        """
        self._on_reconnect = on_reconnect

        while not self._stop_event.is_set():
            try:
                logger.info(f"Conectando a {self._server_url}...")
                self._ws = websocket.WebSocketApp(
                    self._server_url,
                    on_open=    self._on_open,
                    on_message= self._on_message,
                    on_error=   self._on_error,
                    on_close=   self._on_close,
                )
                self._ws.run_forever(ping_interval=10, ping_timeout=5)
            except Exception as e:
                logger.error(f"Error en WebSocket: {e}")

            if self._stop_event.is_set():
                break

            # Backoff exponencial
            logger.info(f"Reconectando en {self._backoff:.0f}s...")
            self._stop_event.wait(timeout=self._backoff)
            self._backoff = min(self._backoff * 2, self.MAX_BACKOFF)

    def stop(self) -> None:
        """Detiene el cliente WebSocket."""
        self._stop_event.set()
        if self._ws:
            self._ws.close()

    # ── Callbacks WebSocket ───────────────────────────────────────────────

    def _on_open(self, ws) -> None:
        self._connected = True
        self._backoff   = 1.0   # resetear backoff al conectar
        logger.info("WebSocket conectado")

        # Enviar module_connect con lista de cámaras
        message = {
            "type":      "module_connect",
            "module_id": self._module_id,
            "version":   "1.0.0",
            "cameras":   self._cameras,
        }
        ws.send(json.dumps(message))

        # Llamar callback de reconexión para vaciar cola local
        if self._on_reconnect:
            self._on_reconnect()

        # Iniciar heartbeat en thread separado
        threading.Thread(
            target=self._heartbeat_loop,
            args=(ws,),
            daemon=True,
        ).start()

    def _on_message(self, ws, message: str) -> None:
        try:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "connected":
                logger.info(f"Servidor confirmó conexión: {data}")

            elif msg_type == "set_camera":
                camera_id = data.get("camera_id")
                logger.info(f"Servidor solicita cámara: {camera_id}")
                if self._on_set_camera:
                    self._on_set_camera(camera_id)

            elif msg_type == "config_update":
                config = data.get("config", {})
                logger.info(f"Servidor envía config: {config}")
                if self._on_config_update:
                    self._on_config_update(config)

            elif msg_type == "upload_url":
                # Manejado por S3ClipUploader directamente via HTTP
                pass

            else:
                logger.warning(f"Mensaje desconocido: {msg_type}")

        except json.JSONDecodeError as e:
            logger.error(f"Error parseando mensaje: {e}")

    def _on_error(self, ws, error) -> None:
        logger.error(f"WebSocket error: {error}")
        self._connected = False

    def _on_close(self, ws, close_status_code, close_msg) -> None:
        logger.warning(f"WebSocket cerrado: {close_status_code} {close_msg}")
        self._connected = False

    # ── Heartbeat ─────────────────────────────────────────────────────────

    def _heartbeat_loop(self, ws) -> None:
        """Envía heartbeat cada HEARTBEAT_INTERVAL segundos."""
        while self._connected and not self._stop_event.is_set():
            time.sleep(self.HEARTBEAT_INTERVAL)
            if not self._connected:
                break
            try:
                message = {
                    "type":      "heartbeat",
                    "module_id": self._module_id,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
                ws.send(json.dumps(message))
                logger.debug("Heartbeat enviado")
            except Exception as e:
                logger.error(f"Error enviando heartbeat: {e}")
                break