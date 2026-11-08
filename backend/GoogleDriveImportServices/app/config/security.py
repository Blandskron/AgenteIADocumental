from dataclasses import dataclass, field
from pathlib import Path
import re

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidKeyError, InvalidTokenError
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.exceptions import UnsupportedAlgorithm
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config.settings import Settings, get_settings

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class DriveUser:
    user_id: str
    fingerprint: str = field(repr=False)
    tenant_id: str | None = None


def read_public_key(path: str | Path) -> str:
    try:
        content = Path(path).read_text(encoding="utf-8")
        key = load_pem_public_key(content.encode("utf-8"))
        if not isinstance(key, RSAPublicKey) or key.key_size < 2048:
            raise ValueError
        return content
    except (OSError, ValueError, UnicodeError, UnsupportedAlgorithm):
        raise RuntimeError("Drive verification key is unavailable or invalid.") from None


def require_authenticated_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> DriveUser:
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

    tenant = payload.get("active_tenant_id")
    if tenant is not None and (type(tenant) is not str or not 1 <= len(tenant) <= 128):
        raise HTTPException(status_code=401, detail="Invalid authentication token.")
    user = DriveUser(identifier, payload["hash_password"], tenant)
    # Finish this transaction before provider calls; never hold identity locks over network I/O.
    with request.app.state.database.session() as session:
        check_identity(session, user)
    return user


def check_identity(session: Session, user: DriveUser):
    try:
        if not session.scalar(text("SELECT public.drive_identity_is_current(:identifier,:fingerprint)"),
                              {"identifier": int(user.user_id), "fingerprint": user.fingerprint}):
            raise HTTPException(status_code=401, detail="Invalid authentication token.", headers={"WWW-Authenticate": "Bearer"})
        if not session.scalar(text("SELECT public.drive_access_is_allowed(:identifier,:tenant)"),
                              {"identifier": int(user.user_id), "tenant": user.tenant_id}):
            raise HTTPException(status_code=403, detail="Google Drive permission required for the active tenant.")
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Drive identity verification is unavailable.") from None


def owner_user_id(user: DriveUser) -> str:
    return user.user_id


def bearer_token(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)):
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication token required.")
    return credentials.credentials
