from contextlib import closing

from app.application.documents.ports.document_access_repository import DocumentAccessRepository
from app.domain.documents import DocumentDeleteResult
from app.infrastructure.storage.document_path_resolver import LocalDocumentPathResolver
from app.shared.errors import ValidationError


class CleanupDocumentDeletion:
    def __init__(self, repository: DocumentAccessRepository, path_resolver: LocalDocumentPathResolver) -> None:
        self._repository = repository
        self._path_resolver = path_resolver

    def execute(self, document_id: str, skip_locked: bool = False) -> DocumentDeleteResult | None:
        deletion = self._repository.claim_deletion(document_id, skip_locked=skip_locked)
        if deletion is None:
            self._repository.release_deletion()
            return None
        if deletion.completed_at is not None:
            self._repository.release_deletion()
            return DocumentDeleteResult(deletion.document_id, deletion.filename, True, deletion.file_deleted)

        file_deleted = False
        try:
            path = self._path_resolver.resolve_for_deletion(deletion.storage_path)
            if self._is_referenced(path):
                self._repository.defer_deletion(document_id, "SharedReference")
                return DocumentDeleteResult(deletion.document_id, deletion.filename, True, False)
            try:
                path.unlink()
                file_deleted = True
            except FileNotFoundError:
                pass
            self._repository.complete_deletion(document_id, file_deleted)
        except (OSError, ValidationError) as exc:
            self._repository.defer_deletion(document_id, type(exc).__name__)
        return DocumentDeleteResult(deletion.document_id, deletion.filename, True, file_deleted)

    def _is_referenced(self, path) -> bool:
        is_link = path.is_symlink()
        with closing(self._repository.storage_paths()) as locations:
            for location in locations:
                try:
                    if is_link and self._path_resolver.resolve_for_deletion(location) == path:
                        return True
                    if not is_link and path.samefile(self._path_resolver.resolve(location)):
                        return True
                except (FileNotFoundError, ValidationError):
                    continue
        return False
