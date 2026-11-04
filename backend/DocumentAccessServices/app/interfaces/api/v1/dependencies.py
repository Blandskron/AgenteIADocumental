from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.documents.use_cases.delete_document import DeleteDocument
from app.application.documents.use_cases.get_document_content import GetDocumentContent
from app.application.documents.use_cases.get_document_file import GetDocumentFile
from app.config.database import get_session
from app.config.security import require_authenticated_user
from app.config.settings import Settings, get_settings
from app.infrastructure.database.repositories import DocumentAccessRepositoryPg
from app.infrastructure.storage.document_path_resolver import LocalDocumentPathResolver


def get_path_resolver(settings: Settings = Depends(get_settings)) -> LocalDocumentPathResolver:
    return LocalDocumentPathResolver(settings.document_storage_base_path)


def get_document_access_repository(
    session: Session = Depends(get_session),
    current_user: dict = Depends(require_authenticated_user),
) -> DocumentAccessRepositoryPg:
    return DocumentAccessRepositoryPg(session, current_user=current_user)


def get_document_file(
    session: Session = Depends(get_session),
    current_user: dict = Depends(require_authenticated_user),
    path_resolver: LocalDocumentPathResolver = Depends(get_path_resolver),
) -> GetDocumentFile:
    return GetDocumentFile(DocumentAccessRepositoryPg(session, current_user=current_user), path_resolver)


def get_document_content(
    session: Session = Depends(get_session),
    current_user: dict = Depends(require_authenticated_user),
) -> GetDocumentContent:
    return GetDocumentContent(DocumentAccessRepositoryPg(session, current_user=current_user))


def get_delete_document(
    session: Session = Depends(get_session),
    current_user: dict = Depends(require_authenticated_user),
    path_resolver: LocalDocumentPathResolver = Depends(get_path_resolver),
) -> DeleteDocument:
    return DeleteDocument(DocumentAccessRepositoryPg(session, current_user=current_user), path_resolver)
