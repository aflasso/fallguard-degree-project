"""
Schemas Pydantic para usuarios.
"""

from pydantic import BaseModel
from typing import Optional


class CreateUserSchema(BaseModel):
    user_id:   str
    email:     str
    fcm_token: Optional[str] = None


class UpdateFCMTokenSchema(BaseModel):
    fcm_token: str