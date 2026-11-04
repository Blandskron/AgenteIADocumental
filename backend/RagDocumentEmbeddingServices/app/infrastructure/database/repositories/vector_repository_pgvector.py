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

        try:
            self.delete_by_document_id(document_id, commit=False)
            for chunk, vector in zip(chunks, vectors, strict=True):
                self._session.add(
                    DocumentEmbeddingModel(
                        document_id=chunk.document_id,
                        chunk_index=chunk.chunk_index,
                        chunk_content=chunk.content,
                        embedding=vector,
                        embedding_model=embedding_model,
                        metadata_=chunk.metadata or {},
                    )
                )
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

    def delete_by_document_id(self, document_id: str, commit: bool = True) -> None:
        self._session.query(DocumentEmbeddingModel).filter(DocumentEmbeddingModel.document_id == document_id).delete(
            synchronize_session=False
        )
        if commit:
            self._session.commit()
