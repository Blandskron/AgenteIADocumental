from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config.database import get_session
from app.infrastructure.database.models import DocumentDeletionModel, DocumentModel

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/db")
def health_db(session: Session = Depends(get_session)) -> dict[str, str]:
    try:
        session.scalar(select(DocumentModel.document_id).limit(1))
        session.scalar(select(DocumentDeletionModel.document_id).limit(1))
        session.execute(text("SELECT * FROM public.access_active_user(NULL::bigint)"))
        session.execute(text("SELECT * FROM public.access_active_tenant(NULL::text)"))
        session.execute(text("SELECT * FROM public.access_active_membership(NULL::text, NULL::text)"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Document access database is unavailable.") from exc
    return {"status": "ok"}
