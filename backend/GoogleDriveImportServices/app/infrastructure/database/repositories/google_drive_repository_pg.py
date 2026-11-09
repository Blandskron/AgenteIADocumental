from contextlib import contextmanager
from typing import Any

from sqlalchemy import desc, select, text
from app.config.security import DriveUser, check_identity

from app.infrastructure.database.connection import Database
from app.shared.errors import NotFoundError
from app.infrastructure.database.models import (
    GoogleDriveConnectionModel,
    GoogleDriveImportFileModel,
    GoogleDriveImportModel,
)


from app.infrastructure.database.repositories.credential_repository import CredentialRepository


class GoogleDriveRepository(CredentialRepository):
    def __init__(self, database: Database, current_user: DriveUser) -> None:
        self._database = database
        self._user = current_user

    @contextmanager
    def _session(self):
        with self._database.session() as session:
            check_identity(session, self._user)
            yield session

    def check_identity(self):
        # The short transaction ends before any provider request.
        with self._session():
            pass

    def _require_owner(self, owner_user_id):
        if owner_user_id != self._user.user_id:
            raise NotFoundError("Google Drive resource not found.")

    def _owned_import(self, session, import_id):
        record = session.scalar(select(GoogleDriveImportModel).where(
            GoogleDriveImportModel.import_id == import_id,
            GoogleDriveImportModel.owner_user_id == self._user.user_id))
        if record is None:
            raise NotFoundError("Google Drive import not found.")
        return record

    def get_connection(self, owner_user_id: str) -> GoogleDriveConnectionModel | None:
        self._require_owner(owner_user_id)
        with self._session() as session:
            return session.scalar(
                select(GoogleDriveConnectionModel).where(GoogleDriveConnectionModel.owner_user_id == owner_user_id),
            )

    def create_import(self, owner_user_id: str, total_files: int, metadata: dict[str, Any]) -> GoogleDriveImportModel:
        self._require_owner(owner_user_id)
        with self._session() as session:
            record = GoogleDriveImportModel(
                owner_user_id=owner_user_id,
                status="RUNNING",
                total_files=total_files,
                processed_files=0,
                failed_files=0,
                metadata_=metadata,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    def get_import(self, owner_user_id: str, import_id: str) -> GoogleDriveImportModel | None:
        self._require_owner(owner_user_id)
        with self._session() as session:
            return session.scalar(
                select(GoogleDriveImportModel).where(
                    GoogleDriveImportModel.owner_user_id == owner_user_id,
                    GoogleDriveImportModel.import_id == import_id,
                ),
            )

    def list_imports(self, owner_user_id: str, limit: int) -> list[GoogleDriveImportModel]:
        self._require_owner(owner_user_id)
        with self._session() as session:
            return list(
                session.scalars(
                    select(GoogleDriveImportModel)
                    .where(GoogleDriveImportModel.owner_user_id == owner_user_id)
                    .order_by(desc(GoogleDriveImportModel.created_at))
                    .limit(limit),
                ),
            )

    def add_import_file(self, import_id: str, payload: dict[str, Any]) -> GoogleDriveImportFileModel:
        with self._session() as session:
            self._owned_import(session, import_id)
            record = GoogleDriveImportFileModel(import_id=import_id, **payload)
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    def update_import_file(self, import_file_id: str, payload: dict[str, Any]) -> GoogleDriveImportFileModel | None:
        with self._session() as session:
            record = session.scalar(select(GoogleDriveImportFileModel).join(
                GoogleDriveImportModel, GoogleDriveImportFileModel.import_id == GoogleDriveImportModel.import_id).where(
                GoogleDriveImportFileModel.import_file_id == import_file_id,
                GoogleDriveImportModel.owner_user_id == self._user.user_id))
            if record is None:
                raise NotFoundError("Google Drive file not found.")
            for key, value in payload.items():
                setattr(record, key, value)
            session.commit()
            session.refresh(record)
            return record

    def list_import_files(self, import_id: str) -> list[GoogleDriveImportFileModel]:
        with self._session() as session:
            self._owned_import(session, import_id)
            return list(
                session.scalars(
                    select(GoogleDriveImportFileModel)
                    .where(GoogleDriveImportFileModel.import_id == import_id)
                    .order_by(GoogleDriveImportFileModel.created_at),
                ),
            )

    def finish_import(self, import_id: str, processed_files: int, failed_files: int, status: str, error_message: str | None) -> GoogleDriveImportModel | None:
        with self._session() as session:
            record = self._owned_import(session, import_id)
            record.processed_files = processed_files
            record.failed_files = failed_files
            record.status = status
            record.error_message = error_message
            session.commit()
            session.refresh(record)
            return record

    def owns_folder(self, folder_id: str, owner_user_id: str) -> bool:
        self._require_owner(owner_user_id)
        with self._session() as session:
            return bool(session.scalar(text("SELECT public.drive_owns_folder(:folder,:owner)"),
                                       {"folder": folder_id, "owner": owner_user_id}))

    def associate_document_with_folder(self, folder_id: str, document_id: str, owner_user_id: str) -> None:
        self._require_owner(owner_user_id)
        with self._session() as session:
            if not session.scalar(text("SELECT public.drive_associate_document(:folder,:document,:owner)"),
                                  {"folder": folder_id, "document": document_id, "owner": owner_user_id}):
                raise NotFoundError("Document or folder is no longer available.")
            session.commit()
