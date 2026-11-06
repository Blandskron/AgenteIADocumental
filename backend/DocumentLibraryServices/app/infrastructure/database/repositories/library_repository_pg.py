from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config.security import is_superadmin_user, tenant_ids_for_role, tenant_memberships, user_groups, user_id
from app.shared.errors import ConflictError, NotFoundError, ValidationError
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

    def list_folders(self, parent_folder_id: str | None = None, limit: int = 50, offset: int = 0) -> dict:
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
            .order_by(DocumentFolderModel.name.asc(), DocumentFolderModel.folder_id.asc())
            .limit(limit + 1).offset(offset)
            .all()
        )
        folders = []
        for folder, document_count in rows[:limit]:
            folder.document_count = int(document_count or 0)
            folders.append(folder)
        return {"items": folders, "limit": limit, "offset": offset, "has_more": len(rows) > limit}

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
        self._commit_folder()
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
        self._commit_folder()
        self._session.refresh(folder)
        return folder

    def _commit_folder(self) -> None:
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
            if constraint in ("document_folders_owner_root_name_unique", "document_folders_owner_child_name_unique"):
                raise ConflictError("Folder name already exists at this level.") from exc
            if constraint in ("document_folders_parent_owner_fkey", "document_folders_parent_folder_id_fkey"):
                raise NotFoundError("Parent folder not found.") from exc
            if constraint == "document_folders_name_nonblank_check":
                raise ValidationError("Folder name must not be blank.") from exc
            raise
        except Exception:
            self._session.rollback()
            raise

    def delete_folder(self, folder_id: str) -> bool:
        with self._write_transaction():
            return self._session.execute(delete(DocumentFolderModel).where(
                DocumentFolderModel.folder_id == folder_id,
                DocumentFolderModel.owner_user_id == self._owner_user_id,
            ).returning(DocumentFolderModel.folder_id)).scalar_one_or_none() is not None

    def list_folder_documents(self, folder_id: str, limit: int = 50, offset: int = 0) -> dict:
        if self._folder(folder_id) is None:
            raise NotFoundError("Folder not found.")
        documents = (
            self._accessible_documents_query()
            .join(DocumentFolderItemModel, DocumentFolderItemModel.document_id == DocumentModel.document_id)
            .filter(
                DocumentFolderItemModel.folder_id == folder_id,
                DocumentFolderItemModel.owner_user_id == self._owner_user_id,
            )
            .order_by(DocumentFolderItemModel.added_at.desc(), DocumentModel.document_id.desc())
            .limit(limit + 1).offset(offset)
            .all()
        )
        return self._document_page(documents, limit, offset)

    def add_document_to_folder(self, folder_id: str, document_id: str) -> bool:
        with self._write_transaction():
            self._lock_document_organization(document_id)
            if not self._lock_document(document_id) or not self._lock_folder(folder_id):
                return False
            self._insert_folder_item(folder_id, document_id)
            return True

    def remove_document_from_folder(self, folder_id: str, document_id: str) -> bool:
        with self._write_transaction():
            self._lock_document_organization(document_id)
            if not self._lock_document(document_id, require_access=False) or not self._lock_folder(folder_id):
                return False
            return self._session.execute(delete(DocumentFolderItemModel).where(
                DocumentFolderItemModel.folder_id == folder_id,
                DocumentFolderItemModel.document_id == document_id,
                DocumentFolderItemModel.owner_user_id == self._owner_user_id,
            ).returning(DocumentFolderItemModel.document_id)).scalar_one_or_none() is not None

    def list_recent(self, limit: int = 50, offset: int = 0) -> dict:
        documents = (
            self._accessible_documents_query()
            .filter(DocumentModel.status == "PROCESSED")
            .order_by(DocumentModel.updated_at.desc(), DocumentModel.document_id.desc())
            .limit(limit + 1).offset(offset)
            .all()
        )
        return self._document_page(documents, limit, offset)

    def list_favorites(self, limit: int = 50, offset: int = 0) -> dict:
        documents = (
            self._accessible_documents_query()
            .join(DocumentFavoriteModel, DocumentFavoriteModel.document_id == DocumentModel.document_id)
            .filter(DocumentFavoriteModel.owner_user_id == self._owner_user_id)
            .order_by(DocumentFavoriteModel.created_at.desc(), DocumentModel.document_id.desc())
            .limit(limit + 1).offset(offset)
            .all()
        )
        return self._document_page(documents, limit, offset)

    def _document_page(self, rows, limit, offset):
        return {"items": self._attach_chunk_counts(rows[:limit]), "limit": limit, "offset": offset, "has_more": len(rows) > limit}

    def document_markers(self, document_ids: list[str]) -> list[dict]:
        favorite = select(1).where(
            DocumentFavoriteModel.document_id == DocumentModel.document_id,
            DocumentFavoriteModel.owner_user_id == self._owner_user_id,
        ).exists()
        rows = self._apply_document_access_filter(self._session.query(DocumentModel.document_id, favorite.label("is_favorite"))).filter(
            DocumentModel.document_id.in_(document_ids),
        ).order_by(DocumentModel.document_id).all()
        return [{"document_id": identifier, "is_favorite": marked} for identifier, marked in rows]

    def add_favorite(self, document_id: str) -> bool:
        with self._write_transaction():
            self._lock_document_organization(document_id)
            if not self._lock_document(document_id):
                return False
            self._session.execute(insert(DocumentFavoriteModel).values(
                document_id=document_id, owner_user_id=self._owner_user_id,
            ).on_conflict_do_nothing(index_elements=["document_id", "owner_user_id"]))
            return True

    def move_document_to_folder(self, document_id: str, folder_id: str | None) -> bool:
        with self._write_transaction():
            self._lock_document_organization(document_id)
            if not self._lock_document(document_id):
                return False
            if folder_id is not None and not self._lock_folder(folder_id):
                return False
            self._session.execute(delete(DocumentFolderItemModel).where(
                DocumentFolderItemModel.document_id == document_id,
                DocumentFolderItemModel.owner_user_id == self._owner_user_id,
            ))
            if folder_id is not None:
                self._insert_folder_item(folder_id, document_id)
            return True

    def remove_favorite(self, document_id: str) -> bool:
        with self._write_transaction():
            self._lock_document_organization(document_id)
            if not self._lock_document(document_id, require_access=False):
                return False
            return self._session.execute(delete(DocumentFavoriteModel).where(
                DocumentFavoriteModel.document_id == document_id,
                DocumentFavoriteModel.owner_user_id == self._owner_user_id,
            ).returning(DocumentFavoriteModel.document_id)).scalar_one_or_none() is not None

    @contextmanager
    def _write_transaction(self):
        try:
            yield
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

    def _lock_document_organization(self, document_id: str) -> None:
        # Protocol shared with GoogleDriveRepository: advisory -> document -> folder -> markers.
        self._session.execute(text("""
            SELECT pg_advisory_xact_lock(hashtextextended(
                'blandskron.library.document:' || :owner || ':' || :document, 0))
        """), {"owner": self._owner_user_id, "document": document_id})

    def _lock_document(self, document_id: str, *, require_access: bool = True) -> bool:
        query = self._accessible_documents_query() if require_access else self._session.query(DocumentModel)
        return query.filter(DocumentModel.document_id == document_id).with_for_update(
            read=True, key_share=True,
        ).populate_existing().first() is not None

    def _lock_folder(self, folder_id: str) -> bool:
        # Root first: a cascading ancestor delete must wait before touching any links.
        identifiers = self._session.scalars(text("""
            WITH RECURSIVE ancestry AS (
                SELECT folder_id, parent_folder_id, 0 AS depth FROM document_folders
                WHERE folder_id=:folder AND owner_user_id=:owner
                UNION ALL
                SELECT p.folder_id, p.parent_folder_id, a.depth + 1
                FROM document_folders p JOIN ancestry a ON p.folder_id=a.parent_folder_id
                WHERE p.owner_user_id=:owner
            )
            SELECT f.folder_id FROM document_folders f JOIN ancestry a ON a.folder_id=f.folder_id
            ORDER BY a.depth DESC FOR KEY SHARE OF f
        """), {"folder": folder_id, "owner": self._owner_user_id}).all()
        return folder_id in identifiers

    def _insert_folder_item(self, folder_id: str, document_id: str) -> None:
        self._session.execute(insert(DocumentFolderItemModel).values(
            folder_id=folder_id, document_id=document_id, owner_user_id=self._owner_user_id,
        ).on_conflict_do_nothing(index_elements=["folder_id", "document_id"]))

    def _folder(self, folder_id: str) -> DocumentFolderModel | None:
        return (
            self._session.query(DocumentFolderModel)
            .filter(DocumentFolderModel.folder_id == folder_id, DocumentFolderModel.owner_user_id == self._owner_user_id)
            .first()
        )

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
        favorites = set(self._session.scalars(select(DocumentFavoriteModel.document_id).where(
            DocumentFavoriteModel.document_id.in_(document_ids), DocumentFavoriteModel.owner_user_id == self._owner_user_id,
        )))
        for document in documents:
            document.chunk_count = counts.get(str(document.document_id), 0)
            document.is_favorite = document.document_id in favorites
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
