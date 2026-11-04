from math import isfinite

from app.application.embeddings.ports.embedding_provider import EmbeddingProvider
from app.application.embeddings.ports.vector_repository import VectorRepository
from app.domain.embeddings import DocumentChunk
from app.shared.constants import EMBEDDING_BATCH_SIZE, EMBEDDING_DIMENSIONS, MAX_DOCUMENT_CHUNKS
from app.shared.errors import ExternalServiceError, ExtractionError


class CreateDocumentEmbeddings:
    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        vector_repository: VectorRepository,
        chunk_size: int,
        chunk_overlap: int,
        embedding_model: str,
    ) -> None:
        self._embedding_provider = embedding_provider
        self._vector_repository = vector_repository
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._embedding_model = embedding_model

    def execute(self, document_id: str, text: str, metadata: dict | None = None) -> list[DocumentChunk]:
        chunks = [
            DocumentChunk(document_id=document_id, chunk_index=index, content=content, metadata=metadata)
            for index, content in enumerate(self._split_text(text))
        ]
        vectors = []
        for start in range(0, len(chunks), EMBEDDING_BATCH_SIZE):
            batch = [chunk.content for chunk in chunks[start:start + EMBEDDING_BATCH_SIZE]]
            embeddings = self._embedding_provider.embed_batch(batch)
            if len(embeddings) != len(batch) or any(
                len(vector) != EMBEDDING_DIMENSIONS or not all(isfinite(value) for value in vector)
                for vector in embeddings
            ):
                raise ExternalServiceError("Embedding provider returned invalid vectors.")
            vectors.extend(embeddings)
        self._vector_repository.replace_document_chunks(
            document_id=document_id,
            chunks=chunks,
            vectors=vectors,
            embedding_model=self._embedding_model,
        )
        return chunks

    def _split_text(self, text: str) -> list[str]:
        text = text.strip()
        if not text:
            raise ExtractionError("Document contains no extractable text.")
        if len(text) <= self._chunk_size:
            return [text]

        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + self._chunk_size, len(text))
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
                if len(chunks) > MAX_DOCUMENT_CHUNKS:
                    raise ExtractionError("Document exceeds the indexing chunk limit.")
            if end == len(text):
                break
            start = max(end - self._chunk_overlap, start + 1)
        return chunks
