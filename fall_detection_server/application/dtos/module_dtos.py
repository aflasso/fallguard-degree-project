"""
DTOs de módulos — datos que los casos de uso necesitan para ejecutarse.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class CameraInfoDTO:
    id:   int
    name: str


@dataclass
class ConnectModuleCommand:
    """Comando para conectar un módulo al servidor."""
    module_id: str
    version:   str
    cameras:   List[CameraInfoDTO] = field(default_factory=list)


@dataclass
class LinkModuleCommand:
    """Comando para vincular un módulo a un usuario."""
    module_id: str
    user_id:   str


@dataclass
class UnlinkModuleCommand:
    """Comando para desvincular un módulo de su usuario."""
    module_id: str
    user_id:   str