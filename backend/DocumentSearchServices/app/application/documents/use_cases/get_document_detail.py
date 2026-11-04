from app.application.documents.ports import DocumentSearchRepository
from app.domain.documents import DocumentNotFoundError, DocumentSummary


class GetDocumentDetail:
    def __init__(self, repository: DocumentSearchRepository) -> None:
        self._repository = repository

    def execute(self, document_id: str) -> DocumentSummary:
        document = self._repository.get_by_id(document_id)
        if document is None:
            raise DocumentNotFoundError(f"Document {document_id} was not found.")
        return document
