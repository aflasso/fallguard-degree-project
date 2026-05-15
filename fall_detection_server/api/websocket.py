"""
Endpoint WebSocket del servidor.
Maneja la conexión y mensajes de los módulos locales.
"""

import json
import logging
from operator import imod

from fastapi import WebSocket, WebSocketDisconnect

from api.schemas import (
    ModuleConnectSchema,
    FallAlertSchema,
    RequestUploadUrlSchema,
    HeartbeatSchema,
)


from application.dtos.module_dtos import ConnectModuleCommand, CameraInfoDTO
from application.dtos.alert_dtos import ProcessFallAlertCommand, GenerateUploadUrlCommand
from application.use_cases.connect_module import ConnectModule
from application.use_cases.handle_fall_alert import HandleFallAlert
from application.use_cases.generate_upload_url import GenerateUploadUrl
from application.use_cases.disconnect_module import DisconnectModule
from infrastructure.websocket.connection_manager import WebSocketConnectionManager

logger = logging.getLogger(__name__)


class WebSocketHandler:
    """
    Maneja el ciclo de vida de una conexión WebSocket con un módulo.
    """

    def __init__(
        self,
        connection_manager:   WebSocketConnectionManager,
        connect_module:       ConnectModule,
        handle_fall_alert:    HandleFallAlert,
        disconnect_module:    DisconnectModule,
        generate_upload_url:  GenerateUploadUrl,
    ):
        self._connection_manager  = connection_manager
        self._connect_module      = connect_module
        self._disconnect_module   = disconnect_module
        self._handle_fall_alert   = handle_fall_alert
        self._generate_upload_url = generate_upload_url

    async def handle(self, websocket: WebSocket) -> None:
        """
        Maneja el ciclo de vida completo de una conexión WebSocket.
        """
        module_id = None

        try:

            await websocket.accept()

            # Esperar el primer mensaje — debe ser module_connect
            raw = await websocket.receive_text()
            data = json.loads(raw)

            if data.get("type") != "module_connect":
                await websocket.close(code=4000)
                return

            # Validar y procesar module_connect
            schema  = ModuleConnectSchema(**data)
            command = ConnectModuleCommand(
                module_id= schema.module_id,
                version=   schema.version,
                cameras=   [CameraInfoDTO(id=c.id, name=c.name) for c in schema.cameras],
            )
            module    = await self._connect_module.execute(command)
            module_id = module.module_id

            # Registrar conexión
            await self._connection_manager.connect(module_id, websocket)

            # Confirmar conexión al módulo
            await websocket.send_text(json.dumps({
                "type":      "connected",
                "module_id": module_id,
            }))

            logger.info(f"Módulo conectado: {module_id}")

            # Loop de mensajes
            while True:
                raw  = await websocket.receive_text()
                data = json.loads(raw)
                await self._handle_message(module_id, data, websocket)

        except WebSocketDisconnect:
            logger.info(f"Módulo desconectado: {module_id}")
        except Exception as e:
            logger.error(f"Error en WebSocket {module_id}: {e}")
        finally:
            if module_id:
                await self._connection_manager.disconnect(module_id)
                await self._disconnect_module.execute(module_id)

    async def _handle_message(
        self,
        module_id: str,
        data:      dict,
        websocket: WebSocket,
    ) -> None:
        """Procesa un mensaje recibido del módulo."""
        msg_type = data.get("type")

        if msg_type == "heartbeat":
            # Solo log — el heartbeat confirma que el módulo sigue vivo
            logger.debug(f"Heartbeat recibido: {module_id}")

        elif msg_type == "fall_alert":
            schema  = FallAlertSchema(**data)
            command = ProcessFallAlertCommand(
                module_id=  schema.module_id,
                timestamp=  schema.timestamp,
                confidence= schema.confidence,
                clip_id=    schema.clip_id,
                clip_url=   schema.clip_url,
            )
            await self._handle_fall_alert.execute(command)

        elif msg_type == "request_upload_url":
            schema  = RequestUploadUrlSchema(**data)
            command = GenerateUploadUrlCommand(
                module_id= schema.module_id,
                clip_id=   schema.clip_id,
            )
            try:
                result = await self._generate_upload_url.execute(command)
                await websocket.send_text(json.dumps({
                    "type":          "upload_url",
                    "clip_id":       schema.clip_id,
                    "presigned_url": result.presigned_url,
                    "public_url":    result.public_url,
                    "expires_in":    result.expires_in,
                }))
            except ValueError as e:
                logger.warning(f"No se pudo generar presigned URL para {schema.clip_id}: {e}")
                await websocket.send_text(json.dumps({
                    "type":    "upload_url_error",
                    "clip_id": schema.clip_id,
                    "error":   str(e),
                }))

        elif msg_type == "config_ack":
            logger.info(f"Config ack recibido: {module_id}")

        else:
            logger.warning(f"Mensaje desconocido de {module_id}: {msg_type}")