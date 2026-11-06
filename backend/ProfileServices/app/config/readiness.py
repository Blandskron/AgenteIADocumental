from pathlib import Path
from tempfile import TemporaryFile

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.security import read_public_key
from app.config.settings import Settings
from app.infrastructure.database.models import UserProfileModel


def check_storage(path: Path, *, prepare: bool = False) -> None:
    if prepare:
        path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir() or path.is_symlink():
        raise RuntimeError("Profile storage is unavailable.")
    # Test actual access, rather than permission bits (which differ on mounted volumes).
    with TemporaryFile(dir=path) as probe:
        probe.write(b"profile-readiness")
        probe.flush()


def check_dependencies(settings: Settings, session: Session, *, prepare: bool = False) -> None:
    read_public_key(settings.auth_jwt_public_key_path)
    session.scalar(select(UserProfileModel.profile_id).limit(1))
    check_storage(settings.profile_uploads_dir, prepare=prepare)
