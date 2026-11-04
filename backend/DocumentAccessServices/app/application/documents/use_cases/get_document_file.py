from pathlib import Path

from app.application.documents.ports.document_access_repository import DocumentAccessRepository
from app.domain.documents import DocumentFile
from app.domain.documents.exceptions import DocumentDownloadNotAllowedError, DocumentNotFoundError
from app.infrastructure.storage.document_path_resolver import LocalDocumentPathResolver


class GetDocumentFile:
    def __init__(self, repository: DocumentAccessRepository, path_resolver: LocalDocumentPathResolver) -> None:
        self._repository = repository
        self._path_resolver = path_resolver

    def execute(self, document_id: str, for_download: bool = False) -> tuple[DocumentFile, Path]:
        document = self._repository.get_by_id(document_id)
        if document is None:
            raise DocumentNotFoundError(f"Document {document_id} was not found.")
        if for_download and not self._repository.can_download(document_id):
            raise DocumentDownloadNotAllowedError("No tienes permisos para descargar este documento.")

        try:
            if for_download:
                self._repository.record_document_event(document_id, "DOCUMENT_DOWNLOADED")
            return document, self._path_resolver.resolve(document.storage_path)
        except FileNotFoundError as exc:
            raise DocumentNotFoundError(f"Document file for {document_id} was not found.") from exc
