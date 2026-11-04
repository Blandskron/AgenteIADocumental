from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.use_cases.manage_transfers import ManageTransfers
from app.config.database import get_session
from app.config.security import require_authenticated_user
from app.infrastructure.database.repositories.transfer_repository_pg import TransferRepositoryPg


def get_transfer_use_case(
    session: Session = Depends(get_session),
    current_user: dict = Depends(require_authenticated_user),
) -> ManageTransfers:
    return ManageTransfers(TransferRepositoryPg(session, current_user))
