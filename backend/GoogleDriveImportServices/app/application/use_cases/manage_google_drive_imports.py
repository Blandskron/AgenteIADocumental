from typing import Any

from app.config.settings import Settings
from app.infrastructure.documents.document_upload_client import DocumentUploadClient
from app.infrastructure.google.drive_client import GoogleDriveClient
from app.infrastructure.google.token_cipher import TokenCipher
from app.shared.errors import NotFoundError, ValidationError


from app.application.use_cases.credential_lifecycle import CredentialLifecycle


class ManageGoogleDriveImports(CredentialLifecycle):
    def __init__(
        self,
        repository,
        google_client: GoogleDriveClient,
        document_client: DocumentUploadClient,
        token_cipher: TokenCipher,
        settings: Settings,
    ) -> None:
        self._repository = repository
        self._google_client = google_client
        self._document_client = document_client
        self._token_cipher = token_cipher
        self._settings = settings

    def import_files(self, owner_user_id: str, bearer_token: str, payload) -> tuple[Any, list[Any]]:
        file_requests = payload.files[: self._settings.max_import_files]
        if not file_requests:
            raise ValidationError("At least one Google Drive file is required.")
        if payload.folder_id and not self._repository.owns_folder(payload.folder_id, owner_user_id):
            raise NotFoundError("Folder not found.")

        connection = self._repository.get_connection(owner_user_id)
        if connection is None:
            raise ValidationError("Google Drive is not connected for this user.")

        access_token = self._valid_access_token(owner_user_id, connection)
        import_record = self._repository.create_import(
            owner_user_id,
            len(file_requests),
            {"source": "google_drive", "folder_id": payload.folder_id, **(payload.metadata or {})},
        )

        processed = 0
        failed = 0
        folder_warnings = 0

        for file_request in file_requests:
            file_record = self._repository.add_import_file(
                import_record.import_id,
                {
                    "google_file_id": file_request.file_id,
                    "filename": file_request.name or file_request.file_id,
                    "mime_type": file_request.mime_type or "application/octet-stream",
                    "export_mime_type": file_request.export_mime_type,
                    "size_bytes": None,
                    "status": "RUNNING",
                    "document_id": None,
                    "metadata_": {"picker_metadata": file_request.model_dump(exclude_none=True)},
                },
            )

            try:
                self._repository.check_identity()
                self._repository.ensure_connection_current(connection.version)
                downloaded = self._google_client.download_file(access_token, file_request.file_id, file_request.export_mime_type)
                self._repository.check_identity()
                self._repository.ensure_connection_current(connection.version)
                upload_response = self._document_client.upload(
                    bearer_token=bearer_token,
                    filename=downloaded.filename,
                    mime_type=downloaded.mime_type,
                    content=downloaded.content,
                    metadata={
                        "source": "google_drive",
                        "google_file_id": file_request.file_id,
                        "google_web_view_link": downloaded.metadata.web_view_link,
                        "google_mime_type": downloaded.metadata.mime_type,
                        "import_id": import_record.import_id,
                        "folder_id": payload.folder_id,
                        **(payload.metadata or {}),
                    },
                )
                document_id = upload_response.get("document_id")
                folder_warning = None
                association = {}
                if payload.folder_id:
                    try:
                        if not document_id:
                            raise ValidationError("Document ID required for folder association.")
                        self._repository.associate_document_with_folder(
                            folder_id=payload.folder_id, document_id=document_id, owner_user_id=owner_user_id,
                        )
                        association = {"folder_association": {"status": "COMPLETED", "folder_id": payload.folder_id}}
                    except Exception:
                        # Upload has already succeeded. Preserve it and expose partial completion.
                        folder_warnings += 1
                        folder_warning = "Documento importado, pero no se pudo agregar a la carpeta seleccionada."
                        association = {"folder_association": {"status": "FAILED", "folder_id": payload.folder_id}}
                self._repository.update_import_file(
                    file_record.import_file_id,
                    {
                        "filename": downloaded.filename,
                        "mime_type": downloaded.mime_type,
                        "export_mime_type": downloaded.export_mime_type,
                        "size_bytes": len(downloaded.content),
                        "status": "COMPLETED",
                        "document_id": document_id,
                        "metadata_": {
                            "google_web_view_link": downloaded.metadata.web_view_link,
                            "document_status": upload_response.get("status"),
                            **association,
                        },
                        "error_message": folder_warning,
                    },
                )
                processed += 1
            except Exception:
                failed += 1
                self._repository.update_import_file(
                    file_record.import_file_id,
                    {"status": "FAILED", "error_message": "Google Drive file import failed."},
                )

        status = "COMPLETED" if failed == 0 and folder_warnings == 0 else "PARTIAL" if processed else "FAILED"
        warning = "Algunos documentos se importaron sin poder agregarse a la carpeta seleccionada." if folder_warnings else None
        finished = self._repository.finish_import(import_record.import_id, processed, failed, status, warning)
        return finished, self._repository.list_import_files(import_record.import_id)

    def list_imports(self, owner_user_id: str, limit: int) -> list[Any]:
        return self._repository.list_imports(owner_user_id, limit)

    def get_import(self, owner_user_id: str, import_id: str) -> Any:
        record = self._repository.get_import(owner_user_id, import_id)
        if record is None:
            raise NotFoundError("Google Drive import not found.")
        return record

    def list_import_files(self, owner_user_id: str, import_id: str) -> list[Any]:
        self.get_import(owner_user_id, import_id)
        return self._repository.list_import_files(import_id)
