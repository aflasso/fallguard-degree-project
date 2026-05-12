"""
Dependencia de autenticación para los endpoints REST.
Verifica el ID token de Firebase en cada request.
"""

import logging
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import auth

logger = logging.getLogger(__name__)

_bearer = HTTPBearer()


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
) -> dict:
    """
    Verifica el Bearer token de Firebase Auth.
    Retorna el token decodificado con uid y demás claims.
    Lanza 401 si el token es inválido o expirado.
    """
    try:
        decoded = auth.verify_id_token(credentials.credentials)
        return decoded
    except auth.ExpiredIdTokenError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except auth.InvalidIdTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")
    except Exception as e:
        logger.warning(f"Error verificando token: {e}")
        raise HTTPException(status_code=401, detail="No autorizado")


def require_same_user(token_uid: str, resource_uid: str) -> None:
    """Lanza 403 si el uid del token no coincide con el uid del recurso."""
    if token_uid != resource_uid:
        raise HTTPException(status_code=403, detail="Acceso denegado")
