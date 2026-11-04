from datetime import datetime
from typing import Any

from sqlalchemy import desc, select, text

from app.infrastructure.database.connection import Database
from app.infrastructure.database.models import (
    GoogleDriveConnectionModel,
    GoogleDriveImportFileModel,
    GoogleDriveImportModel,
)


class GoogleDriveRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def upsert_connection(self, owner_user_id: str, payload: dict[str, Any]) -> GoogleDriveConnectionModel:
        with self._database.session() as session:
            connection = session.scalar(
                select(GoogleDriveConnectionModel).where(GoogleDriveConnectionModel.owner_user_id == owner_user_id),
            )
            if connection is None:
                connection = GoogleDriveConnectionModel(owner_user_id=owner_user_id, **payload)
                session.add(connection)
            else:
                for key, value in payload.items():
                    setattr(connection, key, value)
            session.commit()
            session.refresh(connection)
            return connection

    def get_connection(self, owner_user_id: str) -> GoogleDriveConnectionModel | None:
        with self._database.session() as session:
            return session.scalar(
                select(GoogleDriveConnectionModel).where(GoogleDriveConnectionModel.owner_user_id == owner_user_id),
            )

    def update_connection_tokens(
        self,
        owner_user_id: str,
        access_token_encrypted: str,
        refresh_token_encrypted: str | None,
        expires_at: datetime | None,
    ) -> GoogleDriveConnectionModel | None:
        with self._database.session() as session:
            connection = session.scalar(
                select(GoogleDriveConnectionModel).where(GoogleDriveConnectionModel.owner_user_id == owner_user_id),
            )
            if connection is None:
                return None
            connection.access_token_encrypted = access_token_encrypted
            if refresh_token_encrypted:
                connection.refresh_token_encrypted = refresh_token_encrypted
            connection.expires_at = expires_at
            session.commit()
            session.refresh(connection)
            return connection

    def create_import(self, owner_user_id: str, total_files: int, metadata: dict[str, Any]) -> GoogleDriveImportModel:
        with self._database.session() as session:
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
        with self._database.session() as session:
            return session.scalar(
                select(GoogleDriveImportModel).where(
                    GoogleDriveImportModel.owner_user_id == owner_user_id,
                    GoogleDriveImportModel.import_id == import_id,
                ),
            )

    def list_imports(self, owner_user_id: str, limit: int) -> list[GoogleDriveImportModel]:
        with self._database.session() as session:
            return list(
                session.scalars(
                    select(GoogleDriveImportModel)
                    .where(GoogleDriveImportModel.owner_user_id == owner_user_id)
                    .order_by(desc(GoogleDriveImportModel.created_at))
                    .limit(limit),
                ),
            )

    def add_import_file(self, import_id: str, payload: dict[str, Any]) -> GoogleDriveImportFileModel:
        with self._database.session() as session:
            record = GoogleDriveImportFileModel(import_id=import_id, **payload)
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    def update_import_file(self, import_file_id: str, payload: dict[str, Any]) -> GoogleDriveImportFileModel | None:
        with self._database.session() as session:
            record = session.get(GoogleDriveImportFileModel, import_file_id)
            if record is None:
                return None
            for key, value in payload.items():
                setattr(record, key, value)
            session.commit()
            session.refresh(record)
            return record

    def list_import_files(self, import_id: str) -> list[GoogleDriveImportFileModel]:
        with self._database.session() as session:
            return list(
                session.scalars(
                    select(GoogleDriveImportFileModel)
                    .where(GoogleDriveImportFileModel.import_id == import_id)
                    .order_by(GoogleDriveImportFileModel.created_at),
                ),
            )

    def finish_import(self, import_id: str, processed_files: int, failed_files: int, status: str, error_message: str | None) -> GoogleDriveImportModel | None:
        with self._database.session() as session:
            record = session.get(GoogleDriveImportModel, import_id)
            if record is None:
                return None
            record.processed_files = processed_files
            record.failed_files = failed_files
            record.status = status
            record.error_message = error_message
            session.commit()
            session.refresh(record)
            return record

    def associate_document_with_folder(self, folder_id: str, document_id: str, owner_user_id: str) -> None:
        with self._database.session() as session:
            session.execute(
                text(
                    """
                    INSERT INTO document_folder_items (folder_id, document_id, owner_user_id)
                    VALUES (:folder_id, :document_id, :owner_user_id)
                    ON CONFLICT (folder_id, document_id) DO NOTHING
                    """
                ),
                {"folder_id": folder_id, "document_id": document_id, "owner_user_id": owner_user_id},
            )
            session.commit()
