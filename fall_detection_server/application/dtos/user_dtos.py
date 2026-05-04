"""
DTOs de usuarios.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class CreateUserCommand:
    """Comando para crear un usuario."""
    user_id:   str
    email:     str
    fcm_token: Optional[str] = None


@dataclass
class UpdateFCMTokenCommand:
    """Comando para actualizar el token FCM de un usuario."""
    user_id:   str
    fcm_token: str