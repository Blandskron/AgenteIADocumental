from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.database import get_session
from app.config.settings import Settings, get_settings
from app.infrastructure.database.models import ChatMessageModel

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/db")
def health_db(session: Session = Depends(get_session)) -> dict[str, str]:
    session.scalar(select(ChatMessageModel.message_id).limit(1))
    return {"status": "ok"}


@router.get("/health/ai", responses={503: {"description": "Groq API key not configured."}})
def health_ai(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    if not settings.groq_api_key.strip():
        raise HTTPException(status_code=503, detail="Groq API key not configured.")
    return {"status": "configured"}
