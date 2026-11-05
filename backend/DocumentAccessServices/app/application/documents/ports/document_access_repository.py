from collections.abc import Generator
from typing import Protocol

from app.domain.documents import DocumentContent, DocumentDeletion, DocumentFile


class DocumentAccessRepository(Protocol):
    def get_by_id(self, document_id: str) -> DocumentFile | None:
        """Return a document record by id."""

    def can_download(self, document_id: str) -> bool:
        """Return whether current user can download this document."""

    def record_document_event(self, document_id: str, action: str, metadata: dict | None = None) -> None:
        """Persist audit/event information for a document action."""

    def get_content(self, document_id: str, max_chunks: int = 500) -> DocumentContent | None:
        """Return extracted textual content assembled from stored chunks."""

    def prepare_deletion(self, document_id: str) -> DocumentDeletion | None:
        """Authorize removal and atomically persist the cleanup record."""

    def claim_deletion(self, document_id: str, skip_locked: bool = False) -> DocumentDeletion | None:
        """Lock a cleanup record until completion or release."""

    def complete_deletion(self, document_id: str, file_deleted: bool) -> None:
        """Commit a completed cleanup."""

    def defer_deletion(self, document_id: str, error_code: str) -> None:
        """Persist a retry after a filesystem failure."""

    def release_deletion(self) -> None:
        """Roll back the current cleanup transaction and release its lock."""

    def storage_paths(self) -> Generator[str, None, None]:
        """Stream storage locations still referenced by live documents."""
