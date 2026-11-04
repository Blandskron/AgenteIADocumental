from typing import Protocol

from app.domain.embeddings import DocumentChunk


class VectorRepository(Protocol):
    def replace_document_chunks(
        self,
        document_id: str,
        chunks: list[DocumentChunk],
        vectors: list[list[float]],
        embedding_model: str,
    ) -> None:
        ...

    def delete_by_document_id(self, document_id: str) -> None:
        ...
