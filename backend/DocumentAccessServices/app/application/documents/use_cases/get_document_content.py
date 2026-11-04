from app.application.documents.ports.document_access_repository import DocumentAccessRepository
from app.domain.documents import DocumentContent
from app.domain.documents.exceptions import DocumentNotFoundError


class GetDocumentContent:
    def __init__(self, repository: DocumentAccessRepository) -> None:
        self._repository = repository

    def execute(self, document_id: str, max_chunks: int = 500) -> DocumentContent:
        content = self._repository.get_content(document_id=document_id, max_chunks=max_chunks)
        if content is None:
            raise DocumentNotFoundError(f"Document {document_id} was not found.")
        return content
