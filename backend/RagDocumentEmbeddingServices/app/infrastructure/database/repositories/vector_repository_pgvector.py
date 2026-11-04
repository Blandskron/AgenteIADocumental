from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.domain.embeddings import DocumentChunk
from app.infrastructure.database.models import DocumentEmbeddingModel


class VectorRepositoryPgVector:
    def __init__(self, session: Session) -> None:
        self._session = session

    def replace_document_chunks(
        self,
        document_id: str,
        chunks: list[DocumentChunk],
        vectors: list[list[float]],
        embedding_model: str,
    ) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("Chunks and vectors must have the same length.")

        self._session.execute(
            delete(DocumentEmbeddingModel).where(DocumentEmbeddingModel.document_id == document_id)
        )
        self._session.add_all([
            DocumentEmbeddingModel(
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
                chunk_content=chunk.content,
                embedding=vector,
                embedding_model=embedding_model,
                metadata_=chunk.metadata or {},
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ])
