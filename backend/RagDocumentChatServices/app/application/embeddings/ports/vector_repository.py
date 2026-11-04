from typing import Protocol

from app.domain.embeddings import SearchResult


class VectorRepository(Protocol):
    def search_similar(
        self,
        query_vector: list[float],
        limit: int,
        min_score: float = 0.0,
        document_ids: list[str] | None = None,
    ) -> list[SearchResult]:
        ...

    def get_document_chunks(
        self,
        document_ids: list[str],
        limit_per_document: int,
    ) -> list[SearchResult]:
        ...
