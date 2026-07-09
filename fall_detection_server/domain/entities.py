"""
Entidades del dominio del servidor.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from enum import Enum


class ModuleStatus(Enum):
    CONNECTED    = "connected"
    DISCONNECTED = "disconnected"


class AlertStatus(Enum):
    DETECTED    = "detected"    # caída detectada por el módulo, sin confirmar
    CONFIRMED   = "confirmed"   # usuario confirmó que fue una caída real
    FALSE_ALARM = "falseAlarm"  # usuario descartó como falsa alarma


@dataclass
class CameraInfo:
    id:   int
    name: str


@dataclass
class Module:
    module_id:    str
    status:       ModuleStatus          = ModuleStatus.DISCONNECTED
    last_seen:    Optional[datetime]    = None
    user_id:      Optional[str]         = None
    cameras:      List[CameraInfo]      = field(default_factory=list)
    display_name: Optional[str]         = None

    # Un módulo puede estar CONNECTED (WebSocket vivo, heartbeat llegando) y aun
    # así estar ciego porque su cámara dejó de entregar frames. `status` no
    # alcanza para distinguir esos dos casos.
    camera_ok:            bool               = True
    camera_status_at:     Optional[datetime] = None
    camera_status_reason: Optional[str]      = None

    # Fuente de video que el usuario eligió desde la app. El servidor la empuja
    # al módulo al conectar y cada vez que cambia. `None` = sin configurar: el
    # módulo espera sin detectar.
    camera_url: Optional[str] = None


@dataclass
class User:
    user_id:    str
    email:      str
    fcm_token:  Optional[str] = None


@dataclass
class Alert:
    alert_id:   str
    module_id:  str
    timestamp:  datetime
    confidence: float
    user_id:    Optional[str] = None
    clip_url:   Optional[str] = None
    seen:       bool          = False
    status:     AlertStatus   = AlertStatus.DETECTED