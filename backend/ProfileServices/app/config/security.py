from pathlib import Path

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

from app.config.settings import Settings, get_settings

bearer_scheme = HTTPBearer(auto_error=False)


def read_public_key(path: str | Path) -> str:
    try:
        content = Path(path).read_text(encoding="utf-8")
        key = load_pem_public_key(content.encode("utf-8"))
        if not isinstance(key, RSAPublicKey) or key.key_size < 2048:
            raise ValueError
        return content
    except (OSError, ValueError, UnicodeError):
        raise RuntimeError("Profile verification key is unavailable or invalid.") from None


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
    except (InvalidTokenError, RuntimeError) as exc:
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


def is_admin_user(user: dict) -> bool:
    return is_superadmin_user(user) or bool(tenant_ids_for_role(user, "TENANT_ADMIN"))


def user_groups(user: dict) -> list[str]:
    return list(user.get("groups") or user.get("grupos") or [])
