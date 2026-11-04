from functools import lru_cache
from pathlib import Path

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError

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
            options={"verify_aud": False},
        )
    except (InvalidTokenError, OSError) as exc:
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
    return str(user.get("user_id") or user.get("sub") or user.get("username") or "")


def is_superadmin_user(user: dict) -> bool:
    return bool(user.get("is_superadmin") or user.get("is_superuser") or "SUPERADMIN" in (user.get("roles") or []))


def tenant_memberships(user: dict) -> list[dict]:
    return list(user.get("tenant_memberships") or [])


def active_tenant_id(user: dict) -> str | None:
    value = user.get("active_tenant_id")
    return str(value) if value else None


def active_area_id(user: dict) -> str | None:
    value = user.get("active_area_id")
    return str(value) if value else None


def tenant_ids_for_role(user: dict, *roles: str) -> list[str]:
    wanted = {role.upper() for role in roles}
    return [
        str(membership.get("tenant_id"))
        for membership in tenant_memberships(user)
        if str(membership.get("role") or "").upper() in wanted and membership.get("tenant_id")
    ]


def is_tenant_admin(user: dict, tenant_id: str | None = None) -> bool:
    if is_superadmin_user(user):
        return True
    tenant_ids = tenant_ids_for_role(user, "TENANT_ADMIN")
    return bool(tenant_id in tenant_ids if tenant_id else tenant_ids)


def is_admin_user(user: dict) -> bool:
    return is_superadmin_user(user) or is_tenant_admin(user)


def user_groups(user: dict) -> list[str]:
    return list(user.get("groups") or user.get("grupos") or [])


def build_document_access_metadata(user: dict) -> dict:
    return {
        "tenant_id": active_tenant_id(user),
        "owner_user_id": user_id(user),
        "owner_username": user.get("username") or "",
        "owner_email": user.get("email") or "",
        "owner_area_id": active_area_id(user),
        "owner_groups": user_groups(user),
        "visibility": "group" if user_groups(user) else "private",
    }


def can_access_document(user: dict, metadata: dict | None) -> bool:
    metadata = metadata or {}
    if is_superadmin_user(user):
        return True
    tenant_id = str(metadata.get("tenant_id") or "")
    if tenant_id and is_tenant_admin(user, tenant_id):
        return True
    if not metadata.get("owner_user_id") and not metadata.get("owner_groups"):
        return False
    if user_id(user) == str(metadata.get("owner_user_id") or ""):
        return True
    return bool(set(user_groups(user)) & set(metadata.get("owner_groups") or []))
