"""
DTOs de alertas — datos que los casos de uso necesitan para ejecutarse.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ProcessFallAlertCommand:
    """Comando para procesar una alerta de caída recibida del módulo."""
    module_id:  str
    timestamp:  datetime
    confidence: float
    clip_id:    str
    clip_url:   str


@dataclass
class GenerateUploadUrlCommand:
    """Comando para generar una presigned URL para subir un clip."""
    module_id: str
    clip_id:   str