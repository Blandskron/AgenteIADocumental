from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.use_cases.manage_exports import ManageExports
from app.config.database import get_session
from app.config.security import require_authenticated_user
from app.config.settings import Settings, get_settings
from app.infrastructure.database.repositories.export_repository_pg import ExportRepositoryPg
from app.infrastructure.pdf.chat_pdf_renderer import ChatPdfRenderer


def get_export_use_case(
    session: Session = Depends(get_session),
    current_user: dict = Depends(require_authenticated_user),
    settings: Settings = Depends(get_settings),
) -> ManageExports:
    return ManageExports(
        ExportRepositoryPg(session, current_user),
        ChatPdfRenderer(),
        settings.export_storage_base_path,
    )

