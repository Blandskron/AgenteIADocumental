import json
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request as UrlRequest, build_opener

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
            options={"verify_aud": False, "require": ["exp", "user_id"]},
        )
        if type(payload["user_id"]) is not int or payload["user_id"] <= 0 or type(payload["exp"]) is not int:
            raise InvalidTokenError("Invalid identity or expiration claim.")
    except (InvalidTokenError, OSError, TypeError, OverflowError) as exc:
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

    profile = load_current_profile(credentials.credentials, payload["user_id"], settings.auth_identity_url)
    return {**payload, **profile, "user_id": payload["user_id"], "grupos": profile["groups"], "permisos": profile["permissions"]}


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


def load_current_profile(token: str, identifier: int, url: str) -> dict:
    """Use Auth's existing identity endpoint; never authorize from stale token grants."""
    request = UrlRequest(url, headers={"Authorization": "Bearer " + token, "Accept": "application/json"})
    # Never forward bearer credentials through an environment proxy or a redirect.
    opener = build_opener(ProxyHandler({}), NoIdentityRedirect())
    try:
        with opener.open(request, timeout=5) as response:
            raw = response.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise ValueError()
            profile = json.loads(raw)
        if type(profile) is not dict or type(profile.get("id")) is not int or profile["id"] != identifier:
            raise ValueError()
        for name in ("is_superuser", "is_superadmin", "is_staff"):
            if type(profile.get(name)) is not bool:
                raise ValueError()
        for name in ("groups", "permissions", "roles", "active_permissions"):
            if type(profile.get(name)) is not list or any(type(value) is not str for value in profile[name]):
                raise ValueError()
        for name in ("active_tenant_id", "active_area_id", "active_role"):
            if name not in profile or (profile[name] is not None and type(profile[name]) is not str):
                raise ValueError()
        if type(profile.get("tenant_memberships")) is not list or any(
            type(item) is not dict or type(item.get("tenant_id")) is not str
            or type(item.get("role")) is not str for item in profile["tenant_memberships"]
        ):
            raise ValueError()
    except HTTPError as error:
        if error.code in (401, 403):
            raise HTTPException(status_code=401, detail="Invalid authentication token.",
                                headers={"WWW-Authenticate": "Bearer"}) from None
        raise HTTPException(status_code=503, detail="Auth identity verification is unavailable.") from None
    except (OSError, ValueError, TypeError):
        raise HTTPException(status_code=503, detail="Auth identity verification is unavailable.") from None
    return profile


class NoIdentityRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None
