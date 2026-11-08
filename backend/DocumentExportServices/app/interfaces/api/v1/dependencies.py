from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.use_cases.manage_exports import ManageExports
from app.config.database import get_session
from app.config.security import ExportUser, require_authenticated_user
from app.infrastructure.database.repositories.export_repository_pg import ExportRepositoryPg
from app.infrastructure.pdf.isolated_renderer import IsolatedPdfRenderer


def get_export_use_case(
    session: Session = Depends(get_session),
    current_user: ExportUser = Depends(require_authenticated_user),
) -> ManageExports:
    return ManageExports(
        ExportRepositoryPg(session, current_user),
        IsolatedPdfRenderer(),
    )

