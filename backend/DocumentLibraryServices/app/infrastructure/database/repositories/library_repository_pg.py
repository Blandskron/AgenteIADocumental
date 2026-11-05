from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config.security import is_superadmin_user, tenant_ids_for_role, tenant_memberships, user_groups, user_id
from app.shared.errors import NotFoundError
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
        self._owner_user_id = user_id(self._current_user)

    def list_folders(self, parent_folder_id: str | None = None) -> list[DocumentFolderModel]:
        if parent_folder_id is not None and self._folder(parent_folder_id) is None:
            raise NotFoundError("Folder not found.")
        visible_counts = self._apply_document_access_filter(
            self._session.query(
                DocumentFolderItemModel.folder_id.label("folder_id"),
                func.count(DocumentFolderItemModel.document_id).label("document_count"),
            ).join(DocumentModel, DocumentModel.document_id == DocumentFolderItemModel.document_id)
            .filter(DocumentFolderItemModel.owner_user_id == self._owner_user_id)
        ).group_by(DocumentFolderItemModel.folder_id).subquery()
        rows = (
            self._session.query(DocumentFolderModel, func.coalesce(visible_counts.c.document_count, 0))
            .outerjoin(visible_counts, visible_counts.c.folder_id == DocumentFolderModel.folder_id)
            .filter(
                DocumentFolderModel.owner_user_id == self._owner_user_id,
                DocumentFolderModel.parent_folder_id == parent_folder_id,
            )
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
        if self._folder(folder_id) is None:
            raise NotFoundError("Folder not found.")
        documents = (
            self._accessible_documents_query()
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
        if self._folder(folder_id) is None:
            return False
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

        current_user_id = user_id(self._current_user)
        assignment = DocumentAssignmentModel
        active_assignment = select(1).where(
            assignment.document_id == DocumentModel.document_id,
            assignment.status.not_in(("CANCELLED", "EXPIRED")),
            or_(assignment.assigned_to_user_id == current_user_id, assignment.assigned_by_user_id == current_user_id),
        ).exists()
        owner_id = func.coalesce(DocumentModel.owner_user_id, DocumentModel.metadata_["owner_user_id"].astext)
        tenant_id = func.coalesce(DocumentModel.tenant_id, DocumentModel.metadata_["tenant_id"].astext)
        clauses = [owner_id == current_user_id, active_assignment]
        admin_tenant_ids = tenant_ids_for_role(self._current_user, "TENANT_ADMIN")
        if admin_tenant_ids:
            clauses.append(tenant_id.in_(admin_tenant_ids))
        groups = user_groups(self._current_user)
        if groups:
            member_tenant_ids = [str(membership["tenant_id"]) for membership in tenant_memberships(self._current_user)
                                 if membership.get("tenant_id")]
            clauses.append(
                or_(tenant_id.is_(None), tenant_id.in_(member_tenant_ids))
                & or_(*(DocumentModel.metadata_.contains({"owner_groups": [group]}) for group in groups))
            )
        return statement.filter(or_(*clauses))
