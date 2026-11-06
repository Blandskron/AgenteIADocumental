from pathlib import Path

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config.database import get_session
from app.config.settings import Settings, get_settings
from app.infrastructure.database.models import (
    DocumentModel, DocumentAssignmentModel, DocumentEmbeddingModel,
    DocumentFolderModel, DocumentFolderItemModel, DocumentFavoriteModel,
)

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
        for model in (DocumentModel, DocumentEmbeddingModel,
                      DocumentFolderModel, DocumentFolderItemModel, DocumentFavoriteModel):
            session.execute(select(model).limit(0))
        session.execute(select(DocumentAssignmentModel.document_id, DocumentAssignmentModel.assigned_to_user_id,
                               DocumentAssignmentModel.assigned_by_user_id, DocumentAssignmentModel.status).limit(0))
        # STRICT calls with NULL can skip execution (and its ACL check), so verify explicitly.
        if not session.scalar(text("SELECT has_function_privilege(current_user, 'public.library_lock_document_reference(text)', 'EXECUTE')")):
            raise ValueError("Reference lock permission required.")
        session.execute(text("SELECT public.library_lock_document_reference(NULL::text)"))
    except (OSError, ValueError, UnsupportedAlgorithm, SQLAlchemyError) as exc:
        raise HTTPException(status_code=503, detail="Document library dependencies are unavailable.") from exc
    return {"status": "ok"}
