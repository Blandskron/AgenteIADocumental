from tempfile import TemporaryFile

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.security import read_public_key
from app.config.settings import Settings
from app.infrastructure.database.models import DocumentExportModel


def check_dependencies(settings: Settings, session: Session, *, prepare: bool = False) -> None:
    read_public_key(settings.auth_jwt_public_key_path)
    session.scalar(select(DocumentExportModel.export_id, DocumentExportModel.storage_path).limit(1))
    path = settings.export_storage_base_path
    if prepare:
        path.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or not path.is_dir():
        raise RuntimeError("Export storage is unavailable.")
    with TemporaryFile(dir=path) as probe:
        probe.write(b"export-readiness")
        probe.flush()
