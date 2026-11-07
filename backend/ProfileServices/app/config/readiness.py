from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config.security import read_public_key
from app.config.settings import Settings
from app.infrastructure.database.models import UserProfileModel


def check_dependencies(settings: Settings, session: Session) -> None:
    read_public_key(settings.auth_jwt_public_key_path)
    session.scalar(select(UserProfileModel.profile_id, UserProfileModel.version, UserProfileModel.avatar_ready,
                          func.octet_length(UserProfileModel.avatar_data)).limit(1))
    session.execute(text("""
        SELECT 1 FROM public.auth_user
        WHERE FALSE AND id = 0 AND is_active IS TRUE AND upper(md5(password)) = ''
    """))
