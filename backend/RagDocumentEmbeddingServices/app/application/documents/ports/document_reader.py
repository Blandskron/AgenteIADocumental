from typing import Protocol

from app.domain.documents import Document


class DocumentReader(Protocol):
    def get_by_id(self, document_id: str) -> Document | None:
        ...

    def get_pending_documents(self, limit: int) -> list[Document]:
        ...
