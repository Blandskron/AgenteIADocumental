import hashlib
import json
from time import monotonic
from typing import Any

from app.application.use_cases.credential_lifecycle import CredentialLifecycle
from app.shared.errors import (
    ImportConnectionConflict,
    NotFoundError,
    UploadRejected,
    ValidationError,
)
from app.infrastructure.google.bounded_transport import TransferBudget
from app.shared.import_limits import MAX_BATCH_BYTES, MAX_FILE_BYTES


class ManageGoogleDriveImports(CredentialLifecycle):
    def __init__(
        self, repository, google_client, document_client, token_cipher, settings
    ):
        self._repository = repository
        self._google_client = google_client
        self._document_client = document_client
        self._token_cipher = token_cipher
        self._settings = settings

    def import_files(self, owner_user_id, bearer_token, payload):
        if not payload.files or len(payload.files) > self._settings.max_import_files:
            raise ValidationError("Import batch exceeds configured limits.")
        fingerprint = hashlib.sha256(
            json.dumps(
                payload.model_dump(),
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
        ).hexdigest()
        replay = self._repository.replay_import(payload.operation_id, fingerprint)
        if replay:
            return replay, self._repository.list_import_files(replay.import_id)
        if payload.folder_id and not self._repository.owns_folder(
            payload.folder_id, owner_user_id
        ):
            raise NotFoundError("Folder not found.")
        connection = self._repository.get_connection(owner_user_id)
        if connection is None:
            raise ValidationError("Google Drive is not connected.")
        if (
            payload.connection_version is not None
            and payload.connection_version != connection.version
        ):
            raise ImportConnectionConflict(
                "The selected Google Drive connection changed."
            )
        lease, started = self._repository.claim_import(
            payload.operation_id, fingerprint, payload, connection.version
        )
        if not started:
            return lease, self._repository.list_import_files(lease.import_id)
        files = self._repository.list_import_files(lease.import_id)
        deadline, budget = monotonic() + 600, TransferBudget(MAX_BATCH_BYTES)
        try:
            access = self._valid_access_token(owner_user_id, connection)
        except Exception:
            # No upload was attempted; retain the journal and mark known failures.
            for file in files:
                self._repository.journal_file(
                    lease,
                    file.import_file_id,
                    {
                        "status": "FAILED",
                        "error_message": "Drive authorization is unavailable.",
                    },
                )
            self._repository.complete_operation(lease)
            raise
        requests = {item.file_id: item for item in payload.files}
        authorization_failed = False
        for file in files:
            request = requests[file.google_file_id]
            downloaded, upload_started, document_id = None, False, None
            try:
                self._guard(lease, connection, deadline)
                if authorization_failed:
                    raise ValidationError("Ingestion authorization must be renewed.")
                if budget.remaining <= 0:
                    raise ValidationError("Import byte budget is exhausted.")
                self._repository.journal_file(
                    lease, file.import_file_id, {"status": "DOWNLOADING"}
                )
                downloaded = self._google_client.download_file(
                    access,
                    request.file_id,
                    request.export_mime_type,
                    maximum=min(MAX_FILE_BYTES, budget.remaining),
                    deadline=deadline,
                    budget=budget,
                )
                self._guard(lease, connection, deadline)
                self._repository.journal_file(
                    lease,
                    file.import_file_id,
                    {
                        "status": "UPLOADING",
                        "filename": downloaded.filename,
                        "mime_type": downloaded.mime_type,
                        "export_mime_type": downloaded.export_mime_type,
                        "size_bytes": downloaded.size_bytes,
                    },
                )
                upload_started = True
                response = self._document_client.upload(
                    bearer_token=bearer_token,
                    filename=downloaded.filename,
                    mime_type=downloaded.mime_type,
                    content=downloaded.content,
                    deadline=deadline,
                    metadata={
                        **payload.metadata,
                        "source": "google_drive",
                        "google_file_id": request.file_id,
                        "google_mime_type": downloaded.metadata.mime_type,
                        "import_id": lease.import_id,
                        "folder_id": payload.folder_id,
                    },
                )
                document_id = response.get("document_id")
                if not isinstance(document_id, str) or not document_id:
                    raise ValidationError(
                        "Upload response does not identify a document."
                    )
                downloaded.close()
                values = {
                    "status": "UPLOADED",
                    "document_id": document_id,
                    "metadata_": {"document_status": response.get("status")},
                }
                self._repository.journal_file(lease, file.import_file_id, values)
                warning = (
                    "Documento cargado; su procesamiento necesita revisión."
                    if response.get("status") == "FAILED"
                    else None
                )
                if response.get("status") not in {"PROCESSED", "FAILED"}:
                    try:
                        self._repository.guard_import(lease)
                        self._document_client.process_document(
                            bearer_token, document_id, deadline=deadline
                        )
                        values["metadata_"]["document_status"] = "PROCESSED"
                    except Exception:
                        warning = (
                            "Documento cargado; su procesamiento necesita revisión."
                        )
                        values["metadata_"]["document_status"] = "REVIEW_REQUIRED"
                if payload.folder_id:
                    try:
                        self._repository.associate_document_with_folder(
                            payload.folder_id, document_id, owner_user_id
                        )
                        values["metadata_"]["folder_association"] = {
                            "status": "COMPLETED",
                            "folder_id": payload.folder_id,
                        }
                    except Exception:
                        warning = "Documento importado, pero no se pudo agregar a la carpeta seleccionada."
                        values["metadata_"]["folder_association"] = {
                            "status": "FAILED",
                            "folder_id": payload.folder_id,
                        }
                values.update(status="COMPLETED", error_message=warning)
                self._repository.journal_file(lease, file.import_file_id, values)
            except Exception as exc:
                if isinstance(exc, UploadRejected):
                    authorization_failed, upload_started = True, False
                # Once upload starts, network/JSON/DB failures cannot prove that no document was created.
                status = (
                    "UPLOADED"
                    if document_id
                    else "REVIEW_REQUIRED"
                    if upload_started
                    else "FAILED"
                )
                values = {
                    "status": status,
                    "error_message": "Import requires review before retrying."
                    if upload_started
                    else "Import failed before document creation.",
                }
                if document_id:
                    values["document_id"] = document_id
                self._repository.journal_file(lease, file.import_file_id, values)
            finally:
                if downloaded is not None:
                    downloaded.close()
        finished = self._repository.complete_operation(lease)
        return finished, self._repository.list_import_files(lease.import_id)

    def _guard(self, lease, connection, deadline):
        if monotonic() >= deadline:
            raise ValidationError("Import time budget is exhausted.")
        self._repository.guard_import(lease)
        self._repository.ensure_connection_current(connection.version)

    def list_imports(self, owner_user_id: str, limit: int) -> list[Any]:
        return self._repository.list_imports(owner_user_id, limit)

    def get_import(self, owner_user_id: str, import_id: str) -> Any:
        record = self._repository.get_import(owner_user_id, import_id)
        if record is None:
            raise NotFoundError("Google Drive import not found.")
        return self._repository.recover_import(import_id)

    def list_import_files(self, owner_user_id: str, import_id: str) -> list[Any]:
        self.get_import(owner_user_id, import_id)
        return self._repository.list_import_files(import_id)
