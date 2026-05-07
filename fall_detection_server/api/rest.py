"""
Endpoints REST del servidor.
Maneja las peticiones HTTP de la app móvil.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Header
from firebase_admin import auth as firebase_auth

from api.schemas import (
    LinkModuleSchema,
    ModuleStatusSchema,
    AlertResponseSchema,
    CreateUserSchema,
    UpdateFCMTokenSchema,
    CameraInfoSchema,
    ChangePasswordSchema,
    ResetPasswordSchema,
)
from api.schemas.alert_schemas import RequestUploadUrlSchema, UpdateAlertStatusSchema
from application.dtos.alert_dtos import GenerateUploadUrlCommand
from application.dtos.module_dtos import LinkModuleCommand
from application.dtos.user_dtos import CreateUserCommand, UpdateFCMTokenCommand
from application.use_cases.generate_upload_url import GenerateUploadUrl
from application.use_cases.link_module import LinkModule
from domain.entities import AlertStatus
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
    ):
        self._module_repo      = module_repository
        self._alert_repo       = alert_repository
        self._user_repo        = user_repository
        self._link_module      = link_module
        self._connection_mgr   = connection_manager
        self._generate_upload_url = generate_upload_url

        # Registrar rutas
        router.post("/modules/link")(self.link_module)
        router.get("/modules/status/{module_id}")(self.module_status)
        router.get("/alerts")(self.get_alerts)
        router.post("/users")(self.create_user)
        router.patch("/users/{user_id}/fcm-token")(self.update_fcm_token)
        router.post("/clips/upload-url")(self.request_upload_url)
        router.patch("/alerts/{alert_id}/seen")(self.update_alert_status)
        router.post("/auth/change-password")(self.change_password)
        router.post("/auth/reset-password")(self.reset_password)

    async def link_module(self, body: LinkModuleSchema) -> dict:
        """Vincula un módulo a un usuario."""
        try:
            command = LinkModuleCommand(
                module_id= body.module_id,
                user_id=   body.user_id,
            )
            await self._link_module.execute(command)
            return {"message": "Módulo vinculado correctamente"}
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    async def module_status(self, module_id: str) -> ModuleStatusSchema:
        """Retorna el estado actual de un módulo."""
        module = await self._module_repo.find_by_id(module_id)
        if module is None:
            raise HTTPException(status_code=404, detail="Módulo no encontrado")

        return ModuleStatusSchema(
            module_id= module.module_id,
            status=    module.status.value,
            last_seen= module.last_seen.isoformat() if module.last_seen else None,
            cameras=   [CameraInfoSchema(id=c.id, name=c.name) for c in module.cameras],
            user_id=   module.user_id,
        )

    async def request_upload_url(self, body: RequestUploadUrlSchema) -> dict:
        """Genera una presigned URL para subir un clip."""
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

    async def get_alerts(self, user_id: str) -> List[AlertResponseSchema]:
        """Retorna el historial de alertas de un usuario."""
        alerts = await self._alert_repo.find_by_user(user_id)
        return [
            AlertResponseSchema(
                alert_id=   a.alert_id,
                module_id=  a.module_id,
                timestamp=  a.timestamp,
                confidence= a.confidence,
                clip_url=   a.clip_url,
                seen=       a.seen,
            )
            for a in alerts
        ]

    async def create_user(self, body: CreateUserSchema) -> dict:
        """Crea un nuevo usuario."""
        from domain.entities import User
        user = User(
            user_id=   body.user_id,
            email=     body.email,
            fcm_token= body.fcm_token,
        )
        await self._user_repo.save(user)
        return {"message": "Usuario creado correctamente"}

    async def update_alert_status(self, alert_id: str, body: UpdateAlertStatusSchema) -> dict:
        """Actualiza el estado de una alerta (seen, confirmed, falseAlarm)."""
        alert = await self._alert_repo.find_by_id(alert_id)
        if alert is None:
            raise HTTPException(status_code=404, detail="Alerta no encontrada")
        try:
            alert.status = AlertStatus(body.status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Estado inválido: {body.status}")
        alert.seen = True
        await self._alert_repo.save(alert)
        return {"message": "Estado actualizado"}

    async def update_fcm_token(self, user_id: str, body: UpdateFCMTokenSchema) -> dict:
        """Actualiza el token FCM de un usuario."""
        user = await self._user_repo.find_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        user.fcm_token = body.fcm_token
        await self._user_repo.save(user)
        return {"message": "FCM token actualizado"}

    # ── Auth ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _verify_token(authorization: Optional[str]) -> dict:
        """Valida el ID token de Firebase y retorna el claim decodificado."""
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Token no provisto")
        token = authorization.split(" ", 1)[1]
        try:
            return firebase_auth.verify_id_token(token)
        except Exception as e:
            logger.warning(f"Token inválido: {e}")
            raise HTTPException(status_code=401, detail="Token inválido")

    async def change_password(
        self,
        body: ChangePasswordSchema,
        authorization: Optional[str] = Header(None),
    ) -> dict:
        """
        Cambia la contraseña del usuario autenticado usando Firebase Admin SDK.
        El cliente debe haber reautenticado al usuario antes de llamar este endpoint.
        Solo aplica para cuentas con provider 'password' (no Google OAuth).
        """
        decoded = self._verify_token(authorization)
        uid = decoded["uid"]

        if len(body.new_password) < 6:
            raise HTTPException(
                status_code=400,
                detail="La contraseña debe tener al menos 6 caracteres",
            )

        try:
            user_record = firebase_auth.get_user(uid)
        except Exception:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        provider_ids = [p.provider_id for p in user_record.provider_data]
        if "password" not in provider_ids:
            raise HTTPException(
                status_code=400,
                detail="Esta cuenta usa un proveedor externo (Google) y no permite cambiar contraseña",
            )

        try:
            firebase_auth.update_user(uid, password=body.new_password)
            logger.info(f"Contraseña actualizada para usuario {uid}")
            return {"message": "Contraseña actualizada correctamente"}
        except Exception as e:
            logger.error(f"Error al actualizar contraseña: {e}")
            raise HTTPException(
                status_code=500,
                detail="No se pudo actualizar la contraseña",
            )

    async def reset_password(self, body: ResetPasswordSchema) -> dict:
        """
        Genera un link de restablecimiento de contraseña.
        Firebase Auth envía automáticamente el correo si el provider 'password'
        está habilitado y el template está configurado en Firebase Console.
        """
        try:
            user_record = firebase_auth.get_user_by_email(body.email)
        except firebase_auth.UserNotFoundError:
            return {"message": "Si el correo existe, recibirás un enlace de restablecimiento"}
        except Exception:
            raise HTTPException(status_code=500, detail="Error verificando el correo")

        provider_ids = [p.provider_id for p in user_record.provider_data]
        if "password" not in provider_ids:
            raise HTTPException(
                status_code=400,
                detail="Esta cuenta usa un proveedor externo (Google)",
            )

        try:
            link = firebase_auth.generate_password_reset_link(body.email)
            logger.info(f"Link de reset generado para {body.email}: {link}")
            return {
                "message": "Si el correo existe, recibirás un enlace de restablecimiento",
                "link": link,
            }
        except Exception as e:
            logger.error(f"Error generando reset link: {e}")
            raise HTTPException(
                status_code=500,
                detail="No se pudo generar el enlace de restablecimiento",
            )