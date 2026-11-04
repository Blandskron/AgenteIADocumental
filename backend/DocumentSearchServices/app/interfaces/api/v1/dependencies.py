from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.documents.use_cases.build_chat_context import BuildChatContext
from app.application.documents.use_cases.get_document_chunks import GetDocumentChunks
from app.application.documents.use_cases.get_document_detail import GetDocumentDetail
from app.application.documents.use_cases.search_documents import SearchDocuments
from app.config.database import get_session
from app.config.security import require_authenticated_user
from app.infrastructure.database.repositories import DocumentSearchRepositoryPg


def get_document_repository(
    session: Session = Depends(get_session),
    current_user: dict = Depends(require_authenticated_user),
) -> DocumentSearchRepositoryPg:
    return DocumentSearchRepositoryPg(session, current_user=current_user)


def get_search_documents(repository: DocumentSearchRepositoryPg = Depends(get_document_repository)) -> SearchDocuments:
    return SearchDocuments(repository)


def get_document_detail(repository: DocumentSearchRepositoryPg = Depends(get_document_repository)) -> GetDocumentDetail:
    return GetDocumentDetail(repository)


def get_document_chunks(repository: DocumentSearchRepositoryPg = Depends(get_document_repository)) -> GetDocumentChunks:
    return GetDocumentChunks(repository)


def get_build_chat_context(repository: DocumentSearchRepositoryPg = Depends(get_document_repository)) -> BuildChatContext:
    return BuildChatContext(repository)
