"""JWT RS256 authentication for KnowledgeStudioServices (STB-06)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt

_bearer = HTTPBearer(auto_error=False)


def require_studio_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticación requerida para Knowledge Studio.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    key_path = Path(os.environ.get("AUTH_JWT_PUBLIC_KEY_PATH", "/app/auth_keys/public.pem"))
    if not key_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Clave pública de verificación JWT no disponible.",
        )
    algorithm = os.environ.get("AUTH_JWT_ALGORITHM", "RS256")
    try:
        payload = jwt.decode(
            credentials.credentials,
            key_path.read_text(encoding="utf-8"),
            algorithms=[algorithm],
            options={"require": ["exp", "user_id"]},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de sesión inválido o expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    if payload.get("token_type") == "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se admite un token de refresco como credencial de acceso.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {
        "user_id": str(payload["user_id"]),
        "active_tenant_id": payload.get("active_tenant_id") or payload.get("tenant_id") or "default",
        "is_superuser": bool(payload.get("is_superuser") or payload.get("is_superadmin")),
    }

