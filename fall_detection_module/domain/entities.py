"""
Entidades del dominio.
No tienen dependencias externas — son objetos de datos puros.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum


class ModuleStatus(Enum):
    WAITING_CAMERA  = "waiting_camera"   # conectado, sin cámara elegida
    RUNNING         = "running"          # detectando
    DISCONNECTED    = "disconnected"     # sin conexión al servidor


@dataclass
class CameraInfo:
    id:   int
    name: str


@dataclass
class FallPrediction:
    """Resultado de una predicción del LSTM para un frame."""
    label:      int    # 0=normal, 1=cayendo, 2=post-caída
    prob_normal:  float
    prob_fall:    float
    prob_post:    float

    @property
    def is_fall(self) -> bool:
        return self.label == 1


@dataclass
class FallEvent:
    """
    Evento de caída confirmado por la lógica de ventana deslizante.
    Se crea cuando min_frames consecutivos superan conf_lstm.
    """
    module_id:    str
    timestamp:    datetime
    confidence:   float          # conf_media de los últimos min_frames
    frame_count:  int            # frames que activaron el evento
    frames:       list = field(default_factory=list)   # frames del buffer circular (para el clip)


@dataclass
class Alert:
    """
    Alerta lista para enviar al servidor.
    Se crea después de grabar y subir el clip.
    """
    module_id:  str
    timestamp:  datetime
    confidence: float
    clip_id:    str
    clip_path:  Optional[str]
    clip_url:   Optional[str] = None   # None hasta que se suba el clip
    sent:       bool = False