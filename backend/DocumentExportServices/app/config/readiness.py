from sqlalchemy import func, select

from app.config.security import read_public_key
from app.infrastructure.database.models import DocumentExportModel


def check_dependencies(settings, session, *, prepare=False):
    read_public_key(settings.auth_jwt_public_key_path)
    session.scalar(select(DocumentExportModel.export_id, DocumentExportModel.pdf_sha256,
                          DocumentExportModel.expires_at, DocumentExportModel.operation_key,
                          DocumentExportModel.request_sha256, func.octet_length(DocumentExportModel.pdf_data)).limit(1))
