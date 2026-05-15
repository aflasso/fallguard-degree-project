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

        self._ws:              Optional[websocket.WebSocketApp] = None
        self._connected:       bool      = False
        self._lock             = threading.Lock()
        self._backoff:         float     = 1.0
        self._stop_event       = threading.Event()
        self._pending_uploads: dict      = {}   # {clip_id: (Event, result_dict)}

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

    def request_upload_url(self, clip_id: str, timeout: int = 30) -> tuple[str, str]:
        """
        Solicita una presigned URL al servidor via WebSocket y espera la respuesta.
        Bloquea el hilo llamador hasta recibir la respuesta o agotar el timeout.
        """
        if not self._connected or self._ws is None:
            raise RuntimeError("No hay conexión WebSocket activa")

        event  = threading.Event()
        result = {"presigned_url": None, "public_url": None}

        with self._lock:
            self._pending_uploads[clip_id] = (event, result)

        try:
            self._ws.send(json.dumps({
                "type":      "request_upload_url",
                "module_id": self._module_id,
                "clip_id":   clip_id,
            }))

            # Espera con polling para detectar desconexión antes del timeout completo
            deadline = time.time() + timeout
            while time.time() < deadline:
                if event.wait(timeout=1.0):
                    break
                if not self._connected:
                    raise RuntimeError("Conexión perdida mientras esperaba presigned URL")
            else:
                raise RuntimeError(f"Timeout esperando presigned URL para {clip_id}")

            if "error" in result:
                raise RuntimeError(f"Servidor rechazó presigned URL: {result['error']}")

            return result["presigned_url"], result["public_url"]
        finally:
            with self._lock:
                self._pending_uploads.pop(clip_id, None)

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

        # Llamar callback de reconexión en thread separado para no bloquear
        # Thread 3 — flush_pending usa request_upload_url que espera respuestas
        # WebSocket, y esas respuestas llegan por este mismo thread
        if self._on_reconnect:
            threading.Thread(
                target=self._on_reconnect,
                name="ReconnectFlush",
                daemon=True,
            ).start()

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
                clip_id = data.get("clip_id")
                with self._lock:
                    pending = self._pending_uploads.get(clip_id)
                if pending:
                    event, result = pending
                    result["presigned_url"] = data.get("presigned_url")
                    result["public_url"]    = data.get("public_url")
                    event.set()

            elif msg_type == "upload_url_error":
                clip_id = data.get("clip_id")
                with self._lock:
                    pending = self._pending_uploads.get(clip_id)
                if pending:
                    event, result = pending
                    result["error"] = data.get("error", "Error desconocido")
                    event.set()

            else:
                logger.warning(f"Mensaje desconocido: {msg_type}")

        except json.JSONDecodeError as e:
            logger.error(f"Error parseando mensaje: {e}")

    def _on_error(self, ws, error) -> None:
        # websocket-client pasa los close frames como errores (ABNF object)
        # opcode=8 es un close frame; extraemos el código de los primeros 2 bytes
        if hasattr(error, 'opcode') and error.opcode == websocket.ABNF.OPCODE_CLOSE:
            if hasattr(error, 'data') and len(error.data) >= 2:
                code = int.from_bytes(error.data[:2], 'big')
                if code == 4001:
                    logger.error("Conexión rechazada por el servidor: API key inválido — deteniendo reconexión")
                    self._stop_event.set()
                    return
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