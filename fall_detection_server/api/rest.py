"""
Endpoints REST del servidor.
Maneja las peticiones HTTP de la app móvil.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from api.auth import verify_token, require_same_user
from api.schemas import (
    LinkModuleSchema,
    ModuleStatusSchema,
    AlertResponseSchema,
    CreateUserSchema,
    UpdateFCMTokenSchema,
    CameraInfoSchema,
)
from api.schemas.alert_schemas import RequestUploadUrlSchema, UpdateAlertStatusSchema
from application.dtos.alert_dtos import GenerateUploadUrlCommand
from application.dtos.module_dtos import LinkModuleCommand
from application.use_cases.generate_upload_url import GenerateUploadUrl
from application.use_cases.link_module import LinkModule
from application.ports.upload_url_generator import UploadUrlGenerator
from domain.entities import AlertStatus
import config
from domain.repositories.module_repository import ModuleRepository
from domain.repositories.alert_repository import AlertRepository
from domain.repositories.user_repository import UserRepository
from infrastructure.websocket.connection_manager import WebSocketConnectionManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


class RestHandler:
    """
    Maneja los endpoints REST de la API.
    """

    def __init__(
        self,
        module_repository:    ModuleRepository,
        alert_repository:     AlertRepository,
        user_repository:      UserRepository,
        link_module:          LinkModule,
        connection_manager:   WebSocketConnectionManager,
        generate_upload_url:  GenerateUploadUrl,
        upload_url_generator: UploadUrlGenerator,
    ):
        self._module_repo          = module_repository
        self._alert_repo           = alert_repository
        self._user_repo            = user_repository
        self._link_module          = link_module
        self._connection_mgr       = connection_manager
        self._generate_upload_url  = generate_upload_url
        self._upload_url_generator = upload_url_generator

        # Registrar rutas
        router.post("/modules/link")(self.link_module)
        router.get("/modules/status/{module_id}")(self.module_status)
        router.get("/alerts")(self.get_alerts)
        router.post("/users")(self.create_user)
        router.patch("/users/{user_id}/fcm-token")(self.update_fcm_token)
        router.post("/clips/upload-url")(self.request_upload_url)
        router.patch("/alerts/{alert_id}/seen")(self.update_alert_status)
        router.get("/clips/read-url")(self.get_clip_read_url)

    async def link_module(
        self,
        body:  LinkModuleSchema,
        token: dict = Depends(verify_token),
    ) -> dict:
        """Vincula un módulo a un usuario."""
        require_same_user(token["uid"], body.user_id)
        try:
            command = LinkModuleCommand(
                module_id= body.module_id,
                user_id=   body.user_id,
            )
            await self._link_module.execute(command)
            return {"message": "Módulo vinculado correctamente"}
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    async def module_status(
        self,
        module_id: str,
        token:     dict = Depends(verify_token),
    ) -> ModuleStatusSchema:
        """Retorna el estado actual de un módulo."""
        module = await self._module_repo.find_by_id(module_id)
        if module is None:
            raise HTTPException(status_code=404, detail="Módulo no encontrado")
        if module.user_id is None:
            raise HTTPException(status_code=403, detail="Módulo no vinculado a ningún usuario")
        require_same_user(token["uid"], module.user_id)

        return ModuleStatusSchema(
            module_id= module.module_id,
            status=    module.status.value,
            last_seen= module.last_seen.isoformat() if module.last_seen else None,
            cameras=   [CameraInfoSchema(id=c.id, name=c.name) for c in module.cameras],
            user_id=   module.user_id,
        )

    async def request_upload_url(
        self,
        body:  RequestUploadUrlSchema,
        token: dict = Depends(verify_token),
    ) -> dict:
        """Genera una presigned URL para subir un clip."""
        module = await self._module_repo.find_by_id(body.module_id)
        if module is None:
            raise HTTPException(status_code=404, detail="Módulo no encontrado")
        if module.user_id is None:
            raise HTTPException(status_code=403, detail="Módulo no vinculado a ningún usuario")
        require_same_user(token["uid"], module.user_id)

        command = GenerateUploadUrlCommand(
            module_id= body.module_id,
            clip_id=   body.clip_id,
        )
        result = await self._generate_upload_url.execute(command)
        return {
            "presigned_url": result.presigned_url,
            "public_url":    result.public_url,
            "expires_in":    result.expires_in,
        }

    async def get_alerts(
        self,
        user_id: str,
        status:  Optional[str] = None,
        token:   dict = Depends(verify_token),
    ) -> List[AlertResponseSchema]:
        """Retorna el historial de alertas de un usuario. Filtro opcional: ?status=detected|confirmed|falseAlarm"""
        require_same_user(token["uid"], user_id)

        if status is not None:
            try:
                filter_status = AlertStatus(status)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Estado inválido: {status}. Valores válidos: detected, confirmed, falseAlarm")
        else:
            filter_status = None

        alerts = await self._alert_repo.find_by_user(user_id)

        if filter_status is not None:
            alerts = [a for a in alerts if a.status == filter_status]

        return [
            AlertResponseSchema(
                alert_id=   a.alert_id,
                module_id=  a.module_id,
                timestamp=  a.timestamp,
                confidence= a.confidence,
                clip_url=   a.clip_url,
                seen=       a.seen,
                status=     a.status.value,
            )
            for a in alerts
        ]

    async def create_user(
        self,
        body:  CreateUserSchema,
        token: dict = Depends(verify_token),
    ) -> dict:
        """Crea un nuevo usuario."""
        require_same_user(token["uid"], body.user_id)
        existing = await self._user_repo.find_by_id(body.user_id)
        if existing is not None:
            raise HTTPException(status_code=409, detail="Usuario ya existe")
        from domain.entities import User
        user = User(
            user_id=   body.user_id,
            email=     body.email,
            fcm_token= body.fcm_token,
        )
        await self._user_repo.save(user)
        return {"message": "Usuario creado correctamente"}

    async def update_alert_status(
        self,
        alert_id: str,
        body:     UpdateAlertStatusSchema,
        token:    dict = Depends(verify_token),
    ) -> dict:
        """Confirma o descarta una alerta. Valores válidos: confirmed, falseAlarm."""
        alert = await self._alert_repo.find_by_id(alert_id)
        if alert is None:
            raise HTTPException(status_code=404, detail="Alerta no encontrada")
        if alert.user_id is None:
            raise HTTPException(status_code=403, detail="Alerta sin usuario asociado")
        require_same_user(token["uid"], alert.user_id)
        allowed = {AlertStatus.CONFIRMED, AlertStatus.FALSE_ALARM}
        try:
            new_status = AlertStatus(body.status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Estado inválido: {body.status}. Valores válidos: confirmed, falseAlarm")
        if new_status not in allowed:
            raise HTTPException(status_code=400, detail=f"Solo se puede actualizar a confirmed o falseAlarm")
        alert.status = new_status
        alert.seen = True
        await self._alert_repo.save(alert)
        return {"message": "Estado actualizado"}

    async def get_clip_read_url(
        self,
        alert_id: str,
        token:    dict = Depends(verify_token),
    ) -> dict:
        """Genera una presigned URL de lectura (GET) para el clip de una alerta."""
        alert = await self._alert_repo.find_by_id(alert_id)
        if alert is None:
            raise HTTPException(status_code=404, detail="Alerta no encontrada")
        if alert.user_id is None:
            raise HTTPException(status_code=403, detail="Alerta sin usuario asociado")
        require_same_user(token["uid"], alert.user_id)
        if not alert.clip_url:
            raise HTTPException(status_code=404, detail="La alerta no tiene clip asociado")

        bucket_prefix = f"https://storage.googleapis.com/{config.GCS_BUCKET_NAME}/"
        blob_name = alert.clip_url.removeprefix(bucket_prefix)

        try:
            read_url = await self._upload_url_generator.generate_read_url(blob_name)
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e))

        return {"read_url": read_url, "expires_in": 900}

    async def update_fcm_token(
        self,
        user_id: str,
        body:    UpdateFCMTokenSchema,
        token:   dict = Depends(verify_token),
    ) -> dict:
        """Actualiza el token FCM de un usuario."""
        require_same_user(token["uid"], user_id)
        user = await self._user_repo.find_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        user.fcm_token = body.fcm_token
        await self._user_repo.save(user)
        return {"message": "FCM token actualizado"}
