from __future__ import annotations

from sqlalchemy import false, func, or_
from sqlalchemy.orm import Session

from app.config.security import is_superadmin_user, tenant_ids_for_role, user_groups, user_id
from app.infrastructure.database.models import (
    DocumentEmbeddingModel,
    DocumentAssignmentModel,
    DocumentFavoriteModel,
    DocumentFolderItemModel,
    DocumentFolderModel,
    DocumentModel,
)


class LibraryRepositoryPg:
    def __init__(self, session: Session, current_user: dict) -> None:
        self._session = session
        self._current_user = current_user or {}
        self._owner_user_id = _owner_user_id(current_user)

    def list_folders(self, parent_folder_id: str | None = None) -> list[DocumentFolderModel]:
        rows = (
            self._session.query(DocumentFolderModel, func.count(DocumentFolderItemModel.document_id).label("document_count"))
            .outerjoin(
                DocumentFolderItemModel,
                (DocumentFolderItemModel.folder_id == DocumentFolderModel.folder_id)
                & (DocumentFolderItemModel.owner_user_id == self._owner_user_id),
            )
            .filter(
                DocumentFolderModel.owner_user_id == self._owner_user_id,
                DocumentFolderModel.parent_folder_id == parent_folder_id,
            )
            .group_by(DocumentFolderModel.folder_id)
            .order_by(DocumentFolderModel.name.asc())
            .all()
        )
        folders = []
        for folder, document_count in rows:
            folder.document_count = int(document_count or 0)
            folders.append(folder)
        return folders

    def create_folder(self, name: str, parent_folder_id: str | None = None, metadata: dict | None = None) -> DocumentFolderModel | None:
        if parent_folder_id is not None and self._folder(parent_folder_id) is None:
            return None
        folder = DocumentFolderModel(
            name=name.strip(),
            parent_folder_id=parent_folder_id,
            owner_user_id=self._owner_user_id,
            metadata_=metadata or {},
        )
        self._session.add(folder)
        self._session.commit()
        self._session.refresh(folder)
        return folder

    def update_folder(self, folder_id: str, name: str | None = None, metadata: dict | None = None) -> DocumentFolderModel | None:
        folder = self._folder(folder_id)
        if folder is None:
            return None
        if name is not None:
            folder.name = name.strip()
        if metadata is not None:
            folder.metadata_ = metadata
        self._session.commit()
        self._session.refresh(folder)
        return folder

    def delete_folder(self, folder_id: str) -> bool:
        folder = self._folder(folder_id)
        if folder is None:
            return False
        self._session.delete(folder)
        self._session.commit()
        return True

    def list_folder_documents(self, folder_id: str) -> list[DocumentModel]:
        documents = (
            self._session.query(DocumentModel)
            .join(DocumentFolderItemModel, DocumentFolderItemModel.document_id == DocumentModel.document_id)
            .filter(
                DocumentFolderItemModel.folder_id == folder_id,
                DocumentFolderItemModel.owner_user_id == self._owner_user_id,
            )
            .order_by(DocumentFolderItemModel.added_at.desc())
            .all()
        )
        return self._attach_chunk_counts(documents)

    def add_document_to_folder(self, folder_id: str, document_id: str) -> bool:
        if self._folder(folder_id) is None or self._accessible_document(document_id) is None:
            return False
        exists = (
            self._session.query(DocumentFolderItemModel)
            .filter(
                DocumentFolderItemModel.folder_id == folder_id,
                DocumentFolderItemModel.document_id == document_id,
                DocumentFolderItemModel.owner_user_id == self._owner_user_id,
            )
            .first()
        )
        if exists is None:
            self._session.add(
                DocumentFolderItemModel(folder_id=folder_id, document_id=document_id, owner_user_id=self._owner_user_id)
            )
            self._session.commit()
        return True

    def remove_document_from_folder(self, folder_id: str, document_id: str) -> bool:
        item = (
            self._session.query(DocumentFolderItemModel)
            .filter(
                DocumentFolderItemModel.folder_id == folder_id,
                DocumentFolderItemModel.document_id == document_id,
                DocumentFolderItemModel.owner_user_id == self._owner_user_id,
            )
            .first()
        )
        if item is None:
            return False
        self._session.delete(item)
        self._session.commit()
        return True

    def list_recent(self, limit: int = 20) -> list[DocumentModel]:
        documents = (
            self._accessible_documents_query()
            .filter(DocumentModel.status == "PROCESSED")
            .order_by(DocumentModel.updated_at.desc())
            .limit(limit)
            .all()
        )
        return self._attach_chunk_counts(documents)

    def list_favorites(self) -> list[DocumentModel]:
        documents = (
            self._accessible_documents_query()
            .join(DocumentFavoriteModel, DocumentFavoriteModel.document_id == DocumentModel.document_id)
            .filter(DocumentFavoriteModel.owner_user_id == self._owner_user_id)
            .order_by(DocumentFavoriteModel.created_at.desc())
            .all()
        )
        return self._attach_chunk_counts(documents)

    def add_favorite(self, document_id: str) -> bool:
        if self._accessible_document(document_id) is None:
            return False
        exists = (
            self._session.query(DocumentFavoriteModel)
            .filter(DocumentFavoriteModel.document_id == document_id, DocumentFavoriteModel.owner_user_id == self._owner_user_id)
            .first()
        )
        if exists is None:
            self._session.add(DocumentFavoriteModel(document_id=document_id, owner_user_id=self._owner_user_id))
        self._session.commit()
        return True

    def move_document_to_folder(self, document_id: str, folder_id: str | None) -> bool:
        if self._accessible_document(document_id) is None:
            return False
        if folder_id is not None and self._folder(folder_id) is None:
            return False

        self._session.query(DocumentFolderItemModel).filter(
            DocumentFolderItemModel.document_id == document_id,
            DocumentFolderItemModel.owner_user_id == self._owner_user_id,
        ).delete(synchronize_session=False)

        if folder_id is not None:
            self._session.add(
                DocumentFolderItemModel(folder_id=folder_id, document_id=document_id, owner_user_id=self._owner_user_id)
            )
        self._session.commit()
        return True

    def remove_favorite(self, document_id: str) -> bool:
        favorite = (
            self._session.query(DocumentFavoriteModel)
            .filter(DocumentFavoriteModel.document_id == document_id, DocumentFavoriteModel.owner_user_id == self._owner_user_id)
            .first()
        )
        if favorite is None:
            return False
        self._session.delete(favorite)
        self._session.commit()
        return True

    def _folder(self, folder_id: str) -> DocumentFolderModel | None:
        return (
            self._session.query(DocumentFolderModel)
            .filter(DocumentFolderModel.folder_id == folder_id, DocumentFolderModel.owner_user_id == self._owner_user_id)
            .first()
        )

    def _accessible_document(self, document_id: str) -> DocumentModel | None:
        return self._accessible_documents_query().filter(DocumentModel.document_id == document_id).first()

    def _attach_chunk_counts(self, documents: list[DocumentModel]) -> list[DocumentModel]:
        document_ids = [str(document.document_id) for document in documents]
        if not document_ids:
            return documents
        rows = (
            self._session.query(DocumentEmbeddingModel.document_id, func.count(DocumentEmbeddingModel.chunk_id))
            .filter(DocumentEmbeddingModel.document_id.in_(document_ids))
            .group_by(DocumentEmbeddingModel.document_id)
            .all()
        )
        counts = {str(document_id): int(count or 0) for document_id, count in rows}
        for document in documents:
            document.chunk_count = counts.get(str(document.document_id), 0)
        return documents

    def _accessible_documents_query(self):
        return self._apply_document_access_filter(self._session.query(DocumentModel))

    def _apply_document_access_filter(self, statement):
        if is_superadmin_user(self._current_user):
            return statement

        clauses = []
        current_user_id = user_id(self._current_user)
        admin_tenant_ids = tenant_ids_for_role(self._current_user, "TENANT_ADMIN")
        if admin_tenant_ids:
            clauses.append(DocumentModel.tenant_id.in_(admin_tenant_ids))
            clauses.append(DocumentModel.metadata_.op("->>")("tenant_id").in_(admin_tenant_ids))
        if current_user_id:
            assigned_document_ids = (
                self._session.query(DocumentAssignmentModel.document_id)
                .filter(DocumentAssignmentModel.assigned_to_user_id == current_user_id)
                .subquery()
            )
            managed_document_ids = (
                self._session.query(DocumentAssignmentModel.document_id)
                .filter(DocumentAssignmentModel.assigned_by_user_id == current_user_id)
                .subquery()
            )
            clauses.append(DocumentModel.owner_user_id == current_user_id)
            clauses.append(DocumentModel.metadata_.op("->>")("owner_user_id") == current_user_id)
            clauses.append(DocumentModel.document_id.in_(assigned_document_ids))
            clauses.append(DocumentModel.document_id.in_(managed_document_ids))
        for group in user_groups(self._current_user):
            clauses.append(DocumentModel.metadata_.contains({"owner_groups": [group]}))
        return statement.filter(or_(*clauses) if clauses else false())


def _owner_user_id(current_user: dict) -> str:
    return str(current_user.get("user_id") or current_user.get("sub") or current_user.get("username") or "unknown")
