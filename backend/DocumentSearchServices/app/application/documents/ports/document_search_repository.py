from typing import Protocol

from app.domain.documents import DocumentChunk, DocumentSearchResult, DocumentSummary


class DocumentSearchRepository(Protocol):
    def search(
        self,
        query: str | None = None,
        status: str | None = None,
        mime_type: str | None = None,
        source: str | None = None,
        limit: int = 20,
        offset: int = 0,
        sort: str = "created_desc",
    ) -> DocumentSearchResult:
        ...

    def get_by_id(self, document_id: str) -> DocumentSummary | None:
        ...

    def get_many_by_ids(self, document_ids: list[str]) -> list[DocumentSummary]:
        ...

    def get_chunks(
        self,
        document_id: str,
        query: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[DocumentChunk], int]:
        ...
