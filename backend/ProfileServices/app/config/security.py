from dataclasses import dataclass
from pathlib import Path
import re

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidKeyError, InvalidTokenError
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.exceptions import UnsupportedAlgorithm
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config.database import get_session
from app.config.settings import Settings, get_settings

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class ProfileUser:
    user_id: str
    groups: tuple[str, ...]
    permissions: tuple[str, ...]


def read_public_key(path: str | Path) -> str:
    try:
        content = Path(path).read_text(encoding="utf-8")
        key = load_pem_public_key(content.encode("utf-8"))
        if not isinstance(key, RSAPublicKey) or key.key_size < 2048:
            raise ValueError
        return content
    except (OSError, ValueError, UnicodeError, UnsupportedAlgorithm):
        raise RuntimeError("Profile verification key is unavailable or invalid.") from None


def require_authenticated_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> ProfileUser:
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
            options={"verify_aud": False, "require": ["exp", "iat", "jti", "user_id", "token_type", "hash_password"]},
        )
        if (type(payload["user_id"]) is not int or not 0 < payload["user_id"] <= 2**63 - 1
                or type(payload["exp"]) is not int or type(payload["iat"]) is not int
                or not 0 <= payload["iat"] < payload["exp"]
                or not isinstance(payload["jti"], str) or not 1 <= len(payload["jti"]) <= 128
                or payload["token_type"] != "access"
                or not isinstance(payload["hash_password"], str)
                or re.fullmatch(r"[0-9A-F]{32}", payload["hash_password"]) is None):
            raise InvalidTokenError()
        identifier = str(payload["user_id"])
        if "sub" in payload and (type(payload["sub"]) is not str or payload["sub"] != identifier):
            raise InvalidTokenError()
        for name in ("is_superuser", "is_superadmin", "is_staff"):
            if name in payload and type(payload[name]) is not bool:
                raise InvalidTokenError()
        for name in ("groups", "grupos", "permissions", "permisos", "user_permissions", "roles"):
            if name in payload and (type(payload[name]) is not list
                                    or any(type(item) is not str for item in payload[name])):
                raise InvalidTokenError()
    except (InvalidTokenError, InvalidKeyError, RuntimeError, TypeError, ValueError, OverflowError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    try:
        # Match SimpleJWT CHECK_REVOKE_TOKEN without returning encoded passwords to the app.
        current = session.scalar(text("""
            SELECT public.profile_identity_is_current(:identifier, :fingerprint)
        """), {"identifier": payload["user_id"], "fingerprint": payload["hash_password"]})
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Profile identity verification is unavailable.") from None
    if not current:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return ProfileUser(identifier, tuple(payload.get("groups", [])), tuple(payload.get("permissions", [])))
