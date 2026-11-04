from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.documents import Document, DocumentStatus
from app.infrastructure.database.models import DocumentModel


class DocumentReaderPg:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, document_id: str) -> Document | None:
        document = self._session.get(DocumentModel, document_id)
        return self._to_document(document) if document else None

    def get_pending_documents(self, limit: int) -> list[Document]:
        statement = (
            select(DocumentModel)
            .where(DocumentModel.status.in_([DocumentStatus.PENDING.value, DocumentStatus.REINDEX_REQUIRED.value]))
            .order_by(DocumentModel.created_at.asc())
            .limit(limit)
        )
        documents = self._session.scalars(statement).all()
        return [self._to_document(document) for document in documents]

    def _to_document(self, document: DocumentModel) -> Document:
        return Document(
            document_id=str(document.document_id),
            filename=document.filename,
            storage_path=document.storage_path,
            mime_type=document.mime_type,
            status=DocumentStatus(document.status),
            metadata=document.metadata_ or {},
        )
