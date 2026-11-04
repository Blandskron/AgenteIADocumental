from app.application.documents.ports import DocumentSearchRepository
from app.domain.documents import DocumentChunk, DocumentNotFoundError


class GetDocumentChunks:
    def __init__(self, repository: DocumentSearchRepository) -> None:
        self._repository = repository

    def execute(
        self,
        document_id: str,
        query: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[DocumentChunk], int]:
        if self._repository.get_by_id(document_id) is None:
            raise DocumentNotFoundError(f"Document {document_id} was not found.")
        return self._repository.get_chunks(
            document_id=document_id,
            query=query,
            limit=max(1, min(limit, 100)),
            offset=max(0, offset),
        )
