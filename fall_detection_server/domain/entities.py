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
    PENDING     = "pending"
    CONFIRMED   = "confirmed"
    FALSE_ALARM = "falseAlarm"


@dataclass
class CameraInfo:
    id:   int
    name: str


@dataclass
class Module:
    module_id:   str
    status:      ModuleStatus          = ModuleStatus.DISCONNECTED
    last_seen:   Optional[datetime]    = None
    user_id:     Optional[str]         = None
    cameras:     List[CameraInfo]      = field(default_factory=list)


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
    status:     AlertStatus   = AlertStatus.PENDING