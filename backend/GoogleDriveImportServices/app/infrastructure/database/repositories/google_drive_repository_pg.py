from contextlib import contextmanager

from sqlalchemy import desc, select, text, tuple_
from app.config.security import DriveUser, check_identity

from app.infrastructure.database.connection import Database
from app.shared.errors import NotFoundError
from app.shared.history_cursor import encode_cursor, decode_cursor
from app.infrastructure.database.models import (
    GoogleDriveConnectionModel,
    GoogleDriveImportFileModel,
    GoogleDriveImportModel,
)


from app.infrastructure.database.repositories.credential_repository import CredentialRepository


from app.infrastructure.database.repositories.import_repository import ImportRepository


class GoogleDriveRepository(CredentialRepository, ImportRepository):
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

    def get_import(self, owner_user_id: str, import_id: str) -> GoogleDriveImportModel | None:
        self._require_owner(owner_user_id)
        with self._session() as session:
            return session.scalar(
                select(GoogleDriveImportModel).where(
                    GoogleDriveImportModel.owner_user_id == owner_user_id,
                    GoogleDriveImportModel.import_id == import_id,
                ),
            )

    def page_imports(self, owner_user_id, limit, before=None):
        self._require_owner(owner_user_id)
        position = decode_cursor(before, "imports", owner_user_id)
        with self._session() as session:
            query = select(GoogleDriveImportModel).where(GoogleDriveImportModel.owner_user_id == owner_user_id)
            if position:
                query = query.where(tuple_(GoogleDriveImportModel.created_at, GoogleDriveImportModel.import_id) < position)
            rows = list(session.scalars(query.order_by(desc(GoogleDriveImportModel.created_at), desc(GoogleDriveImportModel.import_id)).limit(limit+1)))
            visible = rows[:limit]
            return visible, encode_cursor(visible[-1], "imports", owner_user_id) if len(rows)>limit else None

    def page_import_files(self, import_id, limit, after=None):
        position = decode_cursor(after, "files", self._user.user_id, import_id)
        with self._session() as session:
            parent = self._owned_import(session, import_id)
            if parent.status == "PURGED":
                return [], None
            query = select(GoogleDriveImportFileModel).where(GoogleDriveImportFileModel.import_id == import_id)
            if position:
                query = query.where(tuple_(GoogleDriveImportFileModel.created_at, GoogleDriveImportFileModel.import_file_id) > position)
            rows = list(session.scalars(query.order_by(GoogleDriveImportFileModel.created_at, GoogleDriveImportFileModel.import_file_id).limit(limit+1)))
            visible = rows[:limit]
            return visible, encode_cursor(visible[-1], "files", self._user.user_id, import_id) if len(rows)>limit else None

    def list_import_files(self, import_id: str) -> list[GoogleDriveImportFileModel]:
        with self._session() as session:
            parent = self._owned_import(session, import_id)
            if parent.status == "PURGED":
                return []
            return list(
                session.scalars(
                    select(GoogleDriveImportFileModel)
                    .where(GoogleDriveImportFileModel.import_id == import_id)
                    .order_by(GoogleDriveImportFileModel.created_at, GoogleDriveImportFileModel.import_file_id),
                ),
            )

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
