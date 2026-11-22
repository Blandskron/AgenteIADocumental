"""JWT RS256 authentication for AgentOrchestratorServices (AG-004)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config.identity_verifier import (
    IdentityServiceUnavailableError,
    IdentityUnauthorizedError,
    get_default_identity_verifier,
)

_bearer = HTTPBearer(auto_error=False)


def require_agent_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticación requerida para AgentOrchestratorServices.",
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
    identity = {
        "user_id": str(payload["user_id"]),
        "active_tenant_id": payload.get("active_tenant_id") or payload.get("tenant_id") or "default",
        "is_superuser": bool(payload.get("is_superuser") or payload.get("is_superadmin")),
        "raw_token": credentials.credentials,
    }
    auth_identity_url = os.environ.get("AUTH_IDENTITY_URL", "").strip()
    if auth_identity_url:
        try:
            live = get_default_identity_verifier().verify(
                raw_token=credentials.credentials,
                auth_identity_url=auth_identity_url,
            )
            if live.get("user_id"):
                identity["user_id"] = live["user_id"]
            if live.get("active_tenant_id"):
                identity["active_tenant_id"] = live["active_tenant_id"]
            identity["is_superuser"] = bool(live.get("is_superuser", identity["is_superuser"]))
        except IdentityUnauthorizedError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from None
        except IdentityServiceUnavailableError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from None
    return identity

