from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.domain.documents import Document, DocumentStatus
from app.infrastructure.database.models import DocumentModel


class DocumentWriterPg:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        filename: str,
        storage_path: str,
        mime_type: str,
        metadata: dict | None = None,
        status: str = "PENDING",
    ) -> Document:
        document = DocumentModel(
            tenant_id=(metadata or {}).get("tenant_id"),
            owner_user_id=(metadata or {}).get("owner_user_id"),
            owner_area_id=(metadata or {}).get("owner_area_id"),
            created_by_user_id=(metadata or {}).get("owner_user_id"),
            filename=filename,
            storage_path=storage_path,
            mime_type=mime_type,
            metadata_=metadata or {},
            status=status,
        )
        self._session.add(document)
        self._session.flush()
        result = Document(
            document_id=str(document.document_id),
            filename=document.filename,
            storage_path=document.storage_path,
            mime_type=document.mime_type,
            status=DocumentStatus(document.status),
            metadata=document.metadata_ or {},
            owner_user_id=document.owner_user_id,
            tenant_id=document.tenant_id,
        )
        self._session.commit()
        return result

    def mark_as_processing(self, document_id: str) -> None:
        document = self._session.get(DocumentModel, document_id)
        if document:
            document.status = "PROCESSING"
            document.processing_error = None
            self._session.commit()

    def mark_as_processed(self, document_id: str) -> None:
        document = self._session.get(DocumentModel, document_id)
        if document:
            document.status = "PROCESSED"
            document.processed_at = datetime.now(UTC)
            document.processing_error = None
            self._session.commit()

    def mark_as_failed(self, document_id: str, reason: str) -> None:
        document = self._session.get(DocumentModel, document_id)
        if document:
            document.status = "FAILED"
            document.processing_error = reason
            self._session.commit()
