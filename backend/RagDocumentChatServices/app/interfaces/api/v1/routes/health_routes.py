from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.database import get_session
from app.infrastructure.database.models import ChatMessageModel

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/db")
def health_db(session: Session = Depends(get_session)) -> dict[str, str]:
    session.scalar(select(ChatMessageModel.message_id).limit(1))
    return {"status": "ok"}


@router.get("/health/ai")
def health_ai() -> dict[str, str]:
    return {"status": "configured"}
