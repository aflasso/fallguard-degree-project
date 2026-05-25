"""
Punto de entrada del servidor central.
Inicializa Firebase, Firestore y arranca FastAPI con los endpoints
WebSocket y REST.
"""

import logging
import firebase_admin
from firebase_admin import credentials, firestore_async
from fastapi import FastAPI, WebSocket, Query
from fastapi.middleware.cors import CORSMiddleware

from application.use_cases.disconnect_module import DisconnectModule
import config
from infrastructure.firestore.module_repository import FirestoreModuleRepository
from infrastructure.firestore.alert_repository import FirestoreAlertRepository
from infrastructure.firestore.user_repository import FirestoreUserRepository
from infrastructure.firebase.fcm_sender import FCMNotificationSender
from infrastructure.gcs.presigned_url import GCSPresignedUrlGenerator
from infrastructure.websocket.connection_manager import WebSocketConnectionManager
from application.use_cases.connect_module import ConnectModule
from application.use_cases.handle_fall_alert import HandleFallAlert
from application.use_cases.link_module import LinkModule
from application.use_cases.unlink_module import UnlinkModule
from application.use_cases.generate_upload_url import GenerateUploadUrl
from api.websocket import WebSocketHandler
from api.rest import RestHandler, router

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── FastAPI ───────────────────────────────────────────────────────────────────
app = FastAPI(title="Fall Detection Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    logger.info("Iniciando servidor...")

    # ── Firebase ──────────────────────────────────────────────────────────
    cred = credentials.Certificate(config.FIREBASE_CREDENTIALS_PATH)
    firebase_admin.initialize_app(cred)
    db = firestore_async.client()
    logger.info("Firebase inicializado")

    # ── Infraestructura ───────────────────────────────────────────────────
    module_repo        = FirestoreModuleRepository(db)
    alert_repo         = FirestoreAlertRepository(db)
    user_repo          = FirestoreUserRepository(db)
    notification_sender = FCMNotificationSender()
    upload_url_generator = GCSPresignedUrlGenerator()
    connection_manager = WebSocketConnectionManager()

    # ── Casos de uso ──────────────────────────────────────────────────────
    connect_module = ConnectModule(
        module_repository= module_repo,
    )
    handle_fall_alert = HandleFallAlert(
        module_repository=   module_repo,
        alert_repository=    alert_repo,
        user_repository=     user_repo,
        notification_sender= notification_sender,
    )
    link_module = LinkModule(
        module_repository=  module_repo,
        user_repository=    user_repo,
        connection_manager= connection_manager,
    )
    unlink_module = UnlinkModule(
        module_repository=  module_repo,
        connection_manager= connection_manager,
    )
    generate_upload_url = GenerateUploadUrl(
        module_repository=    module_repo,
        upload_url_generator= upload_url_generator,
    )
    disconnect_module = DisconnectModule(
    module_repository= module_repo,
)

    # ── WebSocket handler ─────────────────────────────────────────────────
    ws_handler = WebSocketHandler(
        connection_manager=  connection_manager,
        connect_module=      connect_module,
        disconnect_module=   disconnect_module,
        handle_fall_alert=   handle_fall_alert,
        generate_upload_url= generate_upload_url,
    )

    # ── REST handler ──────────────────────────────────────────────────────
    RestHandler(
        module_repository=    module_repo,
        alert_repository=     alert_repo,
        user_repository=      user_repo,
        link_module=          link_module,
        unlink_module=        unlink_module,
        connection_manager=   connection_manager,
        generate_upload_url=  generate_upload_url,
        upload_url_generator= upload_url_generator,
    )

    app.include_router(router)

    # Guardar ws_handler en el estado de la app para usarlo en el endpoint
    app.state.ws_handler = ws_handler
    logger.info("Servidor listo")


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    api_key:   str = Query(default=""),
):
    if not config.MODULE_API_KEY or api_key != config.MODULE_API_KEY:
        await websocket.accept()
        await websocket.close(code=4001)
        return
    await app.state.ws_handler.handle(websocket)


# ── Correr ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=   config.HOST,
        port=   config.PORT,
        reload= True,
    )