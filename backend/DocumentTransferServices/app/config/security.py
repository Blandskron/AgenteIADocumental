from functools import lru_cache
from pathlib import Path

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidKeyError, InvalidTokenError

from app.config.settings import Settings, get_settings


bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache
def read_public_key(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def require_authenticated_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> dict:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            read_public_key(settings.auth_jwt_public_key_path),
            algorithms=[settings.auth_jwt_algorithm],
            options={"verify_aud": False, "require": ["exp", "user_id"]},
        )
        if type(payload["user_id"]) is not int or payload["user_id"] <= 0 or type(payload["exp"]) is not int:
            raise InvalidTokenError("Invalid identity or expiration claim.")
    except (InvalidTokenError, InvalidKeyError, OSError, TypeError, OverflowError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if payload.get("token_type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


def user_id(user: dict) -> str:
    return str(user["user_id"])


def is_superadmin_user(user: dict) -> bool:
    return bool(user.get("is_superadmin") or user.get("is_superuser") or "SUPERADMIN" in (user.get("roles") or []))


def tenant_memberships(user: dict) -> list[dict]:
    return list(user.get("tenant_memberships") or [])


def tenant_ids_for_role(user: dict, *roles: str) -> list[str]:
    wanted = {role.upper() for role in roles}
    return [
        str(membership.get("tenant_id"))
        for membership in tenant_memberships(user)
        if str(membership.get("role") or "").upper() in wanted and membership.get("tenant_id")
    ]


def user_groups(user: dict) -> list[str]:
    return list(user.get("groups") or user.get("grupos") or [])
