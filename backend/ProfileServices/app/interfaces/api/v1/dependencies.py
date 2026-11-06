from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.use_cases.manage_profile import ManageProfile
from app.config.database import get_session
from app.config.security import ProfileUser, require_authenticated_user
from app.infrastructure.database.repositories.profile_repository_pg import UserProfileRepositoryPg


def get_profile_use_case(
    session: Session = Depends(get_session),
    current_user: ProfileUser = Depends(require_authenticated_user),
) -> ManageProfile:
    return ManageProfile(UserProfileRepositoryPg(session, current_user.user_id))
