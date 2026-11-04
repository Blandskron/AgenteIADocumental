from app.application.embeddings.ports.embedding_provider import EmbeddingProvider
from app.application.embeddings.ports.vector_repository import VectorRepository
from app.domain.embeddings import DocumentChunk


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
        vectors = self._embedding_provider.embed_batch([chunk.content for chunk in chunks])
        self._vector_repository.replace_document_chunks(
            document_id=document_id,
            chunks=chunks,
            vectors=vectors,
            embedding_model=self._embedding_model,
        )
        return chunks

    def _split_text(self, text: str) -> list[str]:
        if len(text) <= self._chunk_size:
            return [text]

        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + self._chunk_size, len(text))
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end == len(text):
                break
            start = max(end - self._chunk_overlap, start + 1)
        return chunks
