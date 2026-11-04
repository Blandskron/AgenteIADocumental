from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.use_cases.manage_library import ManageLibrary
from app.config.database import get_session
from app.config.security import require_authenticated_user
from app.infrastructure.database.repositories.library_repository_pg import LibraryRepositoryPg


def get_library_use_case(
    session: Session = Depends(get_session),
    current_user: dict = Depends(require_authenticated_user),
) -> ManageLibrary:
    return ManageLibrary(LibraryRepositoryPg(session, current_user))
