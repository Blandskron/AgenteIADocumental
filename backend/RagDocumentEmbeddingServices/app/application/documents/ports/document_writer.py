from typing import Protocol

from app.domain.documents import Document


class DocumentWriter(Protocol):
    def create(
        self,
        filename: str,
        storage_path: str,
        mime_type: str,
        metadata: dict | None = None,
        status: str = "PENDING",
    ) -> Document:
        ...

    def mark_as_processing(self, document_id: str) -> None:
        ...

    def mark_as_processed(self, document_id: str) -> None:
        ...

    def mark_as_failed(self, document_id: str, reason: str) -> None:
        ...
