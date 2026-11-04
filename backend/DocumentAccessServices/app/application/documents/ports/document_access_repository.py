from typing import Protocol

from app.domain.documents import DocumentContent, DocumentFile


class DocumentAccessRepository(Protocol):
    def get_by_id(self, document_id: str) -> DocumentFile | None:
        """Return a document record by id."""

    def can_download(self, document_id: str) -> bool:
        """Return whether current user can download this document."""

    def record_document_event(self, document_id: str, action: str, metadata: dict | None = None) -> None:
        """Persist audit/event information for a document action."""

    def get_content(self, document_id: str, max_chunks: int = 500) -> DocumentContent | None:
        """Return extracted textual content assembled from stored chunks."""

    def delete(self, document_id: str) -> None:
        """Delete a document record and its dependent rows."""
