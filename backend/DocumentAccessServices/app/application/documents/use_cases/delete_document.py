from pathlib import Path

from app.application.documents.ports.document_access_repository import DocumentAccessRepository
from app.domain.documents import DocumentDeleteResult
from app.domain.documents.exceptions import DocumentNotFoundError
from app.infrastructure.storage.document_path_resolver import LocalDocumentPathResolver


class DeleteDocument:
    def __init__(self, repository: DocumentAccessRepository, path_resolver: LocalDocumentPathResolver) -> None:
        self._repository = repository
        self._path_resolver = path_resolver

    def execute(self, document_id: str) -> DocumentDeleteResult:
        document = self._repository.get_by_id(document_id)
        if document is None:
            raise DocumentNotFoundError(f"Document {document_id} was not found.")

        file_deleted = self._delete_file(document.storage_path)
        self._repository.delete(document_id)

        return DocumentDeleteResult(
            document_id=document.document_id,
            filename=document.filename,
            deleted=True,
            file_deleted=file_deleted,
        )

    def _delete_file(self, storage_path: str) -> bool:
        try:
            path = self._path_resolver.resolve(storage_path)
        except FileNotFoundError:
            return False

        Path(path).unlink()
        return True
