from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config.database import get_session
from app.config.readiness import check_dependencies
from app.config.settings import Settings, get_settings

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok", "service": "google-drive-import-service"}


@router.get("/health/db")
def readiness(request: Request, settings: Settings = Depends(get_settings), session: Session = Depends(get_session)):
    try:
        check_dependencies(settings, session)
    except Exception:
        raise HTTPException(status_code=503, detail="Drive dependencies are unavailable.") from None
    return {"status": "ok", "enabled": settings.google_drive_enabled}
