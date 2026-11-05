from app.application.documents.ports.document_access_repository import DocumentAccessRepository
from app.application.documents.use_cases.cleanup_document_deletion import CleanupDocumentDeletion
from app.domain.documents import DocumentDeleteResult
from app.domain.documents.exceptions import DocumentNotFoundError
from app.infrastructure.storage.document_path_resolver import LocalDocumentPathResolver


class DeleteDocument:
    def __init__(self, repository: DocumentAccessRepository, path_resolver: LocalDocumentPathResolver) -> None:
        self._repository = repository
        self._cleanup = CleanupDocumentDeletion(repository, path_resolver)

    def execute(self, document_id: str) -> DocumentDeleteResult:
        deletion = self._repository.prepare_deletion(document_id)
        if deletion is None:
            raise DocumentNotFoundError(f"Document {document_id} was not found.")
        result = self._cleanup.execute(document_id)
        if result is None:
            raise DocumentNotFoundError(f"Document {document_id} was not found.")
        return result
