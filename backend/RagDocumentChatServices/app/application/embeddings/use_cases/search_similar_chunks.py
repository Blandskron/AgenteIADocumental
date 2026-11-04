from app.application.embeddings.ports.embedding_provider import EmbeddingProvider
from app.application.embeddings.ports.vector_repository import VectorRepository
from app.domain.embeddings import SearchResult


class SearchSimilarChunks:
    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        vector_repository: VectorRepository,
        limit: int,
        min_score: float = 0.0,
    ) -> None:
        self._embedding_provider = embedding_provider
        self._vector_repository = vector_repository
        self._limit = limit
        self._min_score = min_score

    def execute(self, question: str, document_ids: list[str] | None = None) -> list[SearchResult]:
        query_vector = self._embedding_provider.embed_text(question)
        return self._vector_repository.search_similar(
            query_vector=query_vector,
            limit=self._limit,
            min_score=self._min_score,
            document_ids=document_ids,
        )

    def get_document_context(
        self,
        document_ids: list[str],
        limit_per_document: int = 16,
    ) -> list[SearchResult]:
        return self._vector_repository.get_document_chunks(
            document_ids=document_ids,
            limit_per_document=limit_per_document,
        )
