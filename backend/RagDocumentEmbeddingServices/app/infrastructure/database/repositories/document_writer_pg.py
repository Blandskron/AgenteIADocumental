from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from psycopg.errors import LockNotAvailable
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.domain.documents import Document, DocumentNotFoundError, DocumentStatus
from app.infrastructure.database.models import DocumentModel
from app.shared.errors import AppError, ConflictError


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
        try:
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
        except IntegrityError as exc:
            self._session.rollback()
            if (getattr(exc.orig, "sqlstate", None) == "23503" and
                    getattr(getattr(exc.orig, "diag", None), "constraint_name", None) in {
                        "documents_area_tenant_fk", "documents_owner_area_id_fkey", "documents_tenant_id_fkey"}):
                raise ConflictError("La empresa o el área cambió. Recarga la sesión antes de volver a cargar.") from None
            raise


    @contextmanager
    def indexing_transaction(self, document_id: str) -> Iterator[None]:
        statement = (
            select(DocumentModel)
            .where(DocumentModel.document_id == document_id)
            .with_for_update(nowait=True, key_share=True)
            .execution_options(populate_existing=True)
        )
        try:
            document = self._session.scalar(statement)
        except OperationalError as exc:
            self._session.rollback()
            if isinstance(exc.orig, LockNotAvailable):
                raise ConflictError("Document is already being modified. Retry later.") from exc
            raise
        if document is None:
            self._session.rollback()
            raise DocumentNotFoundError(f"Document {document_id} was not found.")

        was_processed = document.status == DocumentStatus.PROCESSED.value
        try:
            # Keep the row lock when rolling back a failed chunk replacement.
            with self._session.begin_nested():
                yield
                document.status = DocumentStatus.PROCESSED.value
                document.processed_at = datetime.now(UTC)
                document.processing_error = None
        except DocumentNotFoundError:
            self._session.rollback()
            raise
        except Exception as exc:
            if not was_processed:
                document.status = DocumentStatus.FAILED.value
            document.processing_error = str(exc) if isinstance(exc, AppError) else "Document indexing failed."
            self._session.commit()
            raise
        self._session.commit()
