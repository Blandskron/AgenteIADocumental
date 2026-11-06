from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config.database import get_session
from app.config.readiness import check_dependencies
from app.config.settings import Settings, get_settings

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/db")
def health_db(
    session: Session = Depends(get_session), settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    try:
        check_dependencies(settings, session)
    except Exception:
        raise HTTPException(status_code=503, detail="Profile dependencies are unavailable.") from None
    return {"status": "ok"}
