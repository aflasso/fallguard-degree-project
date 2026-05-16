"""
Schemas Pydantic para operaciones de autenticación.
"""

from pydantic import BaseModel


class ChangePasswordSchema(BaseModel):
    new_password: str


class ResetPasswordSchema(BaseModel):
    email: str
