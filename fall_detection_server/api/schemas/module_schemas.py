"""
Schemas Pydantic para mensajes de módulos.
Validan el formato de los mensajes WebSocket y requests REST.
"""

from pydantic import BaseModel
from typing import List, Optional


class CameraInfoSchema(BaseModel):
    id:   int
    name: str


class ModuleConnectSchema(BaseModel):
    type:      str
    module_id: str
    version:   str
    cameras:   List[CameraInfoSchema] = []


class HeartbeatSchema(BaseModel):
    type:      str
    module_id: str
    timestamp: str


class CameraStatusSchema(BaseModel):
    type:      str
    module_id: str
    camera_ok: bool
    reason:    str = ""
    timestamp: Optional[str] = None


class SetCameraSchema(BaseModel):
    camera_id: int


class LinkModuleSchema(BaseModel):
    module_id: str
    user_id:   str


class UnlinkModuleSchema(BaseModel):
    module_id: str
    user_id:   str


class ModuleStatusSchema(BaseModel):
    module_id:    str
    status:       str
    last_seen:    Optional[str] = None
    cameras:      List[CameraInfoSchema] = []
    user_id:      Optional[str] = None
    display_name: Optional[str] = None
    camera_ok:            bool          = True
    camera_status_at:     Optional[str] = None
    camera_status_reason: Optional[str] = None
    camera_url:           Optional[str] = None


class RenameModuleSchema(BaseModel):
    display_name: str


class SetCameraSourceSchema(BaseModel):
    """La validación del esquema de la URL vive en domain/camera_source.py."""
    url: str