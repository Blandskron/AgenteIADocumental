from contextlib import AbstractContextManager
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

    def indexing_transaction(self, document_id: str) -> AbstractContextManager[None]:
        ...
