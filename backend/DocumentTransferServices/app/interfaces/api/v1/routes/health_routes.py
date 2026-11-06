from pathlib import Path

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config.database import get_session
from app.config.settings import Settings, get_settings
from app.infrastructure.database.models import TransferEventModel

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/db")
def health_db(session: Session = Depends(get_session), settings: Settings = Depends(get_settings)) -> dict[str, str]:
    try:
        key = load_pem_public_key(Path(settings.auth_jwt_public_key_path).read_bytes())
        if not isinstance(key, RSAPublicKey):
            raise ValueError("RSA public key required.")
        # Check every mapped column, including an empty table, without reading history.
        session.execute(select(TransferEventModel).limit(0))
    except (OSError, ValueError, UnsupportedAlgorithm, SQLAlchemyError) as exc:
        raise HTTPException(status_code=503, detail="Document transfer dependencies are unavailable.") from exc
    return {"status": "ok"}
