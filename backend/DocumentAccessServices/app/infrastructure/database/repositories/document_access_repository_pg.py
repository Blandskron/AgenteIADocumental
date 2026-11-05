from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config.security import is_superadmin_user, tenant_ids_for_role, tenant_memberships, user_groups, user_id
from app.domain.documents import DocumentContent, DocumentDeletion, DocumentFile
from app.shared.constants import MAX_CONTENT_CHARACTERS
from app.shared.errors import PayloadTooLarge
from app.infrastructure.database.models import (
    AuditLogModel,
    DocumentAssignmentEventModel,
    DocumentAssignmentModel,
    DocumentDeletionModel,
    DocumentEmbeddingModel,
    DocumentModel,
    NotificationModel,
)


class DocumentAccessRepositoryPg:
    def __init__(self, session: Session, current_user: dict | None = None) -> None:
        self._session = session
        self._current_user = current_user or {}

    def get_by_id(self, document_id: str) -> DocumentFile | None:
        document = self._accessible_documents_query().filter(DocumentModel.document_id == document_id).first()
        if document is None:
            return None
        return self._to_file(document)

    def get_content(self, document_id: str, max_chunks: int = 500) -> DocumentContent | None:
        document = self._accessible_documents_query().filter(DocumentModel.document_id == document_id).first()
        if document is None:
            return None

        chunks = (
            self._session.query(
                func.left(DocumentEmbeddingModel.chunk_content, MAX_CONTENT_CHARACTERS + 1).label("chunk_content"),
            )
            .join(DocumentModel, DocumentEmbeddingModel.document_id == DocumentModel.document_id)
            .filter(DocumentEmbeddingModel.document_id == document_id)
        )
        chunks = self._apply_access_filter(chunks).order_by(
            DocumentEmbeddingModel.chunk_index.asc(),
        ).limit(max_chunks)
        parts = []
        character_count = 0
        chunk_count = 0
        with self._session.execute(chunks.statement, execution_options={"yield_per": 1}) as rows:
            for row in rows:
                content = row.chunk_content.strip()
                character_count += len(row.chunk_content)
                if content and parts:
                    character_count += 2
                if character_count > MAX_CONTENT_CHARACTERS:
                    raise PayloadTooLarge("Document content exceeds 2,000,000 characters.")
                if content:
                    parts.append(content)
                chunk_count += 1

        return DocumentContent(
            document_id=str(document.document_id),
            filename=document.filename,
            content="\n\n".join(parts),
            chunk_count=chunk_count,
        )

    def prepare_deletion(self, document_id: str) -> DocumentDeletion | None:
        owner_id = func.coalesce(DocumentModel.owner_user_id, DocumentModel.metadata_["owner_user_id"].astext)
        tenant_id = func.coalesce(DocumentModel.tenant_id, DocumentModel.metadata_["tenant_id"].astext)
        statement = self._session.query(DocumentModel).filter(DocumentModel.document_id == document_id)
        document = self._apply_delete_access_filter(statement, owner_id, tenant_id).with_for_update().populate_existing().first()
        if document is None:
            statement = self._session.query(DocumentDeletionModel).filter(DocumentDeletionModel.document_id == document_id)
            deletion = self._apply_delete_access_filter(
                statement, DocumentDeletionModel.owner_user_id, DocumentDeletionModel.tenant_id,
            ).first()
            result = self._to_deletion(deletion) if deletion is not None else None
            self._session.commit()
            return result

        metadata = document.metadata_ or {}
        owner = document.owner_user_id if document.owner_user_id is not None else metadata.get("owner_user_id")
        tenant = document.tenant_id if document.tenant_id is not None else metadata.get("tenant_id")
        deletion = DocumentDeletionModel(
            document_id=document_id, filename=document.filename, storage_path=document.storage_path,
            owner_user_id=str(owner) if owner is not None else None,
            tenant_id=str(tenant) if tenant is not None else None,
        )
        self._session.add(deletion)
        self._session.add(AuditLogModel(
            tenant_id=document.tenant_id, actor_user_id=user_id(self._current_user),
            action="DOCUMENT_DELETED", resource_type="document", resource_id=document_id,
        ))
        result = self._to_deletion(deletion)
        self._session.query(DocumentModel).filter(DocumentModel.document_id == document_id).delete(synchronize_session=False)
        self._session.commit()
        return result

    def _apply_delete_access_filter(self, statement, owner_id, tenant_id):
        if is_superadmin_user(self._current_user):
            return statement
        return statement.filter(or_(
            owner_id == user_id(self._current_user),
            tenant_id.in_(tenant_ids_for_role(self._current_user, "TENANT_ADMIN")),
        ))

    def claim_deletion(self, document_id: str, skip_locked: bool = False) -> DocumentDeletion | None:
        deletion = self._session.query(DocumentDeletionModel).filter(
            DocumentDeletionModel.document_id == document_id,
        ).with_for_update(skip_locked=skip_locked).populate_existing().first()
        return self._to_deletion(deletion) if deletion is not None else None

    def complete_deletion(self, document_id: str, file_deleted: bool) -> None:
        self._session.query(DocumentDeletionModel).filter(DocumentDeletionModel.document_id == document_id).update({
            "completed_at": datetime.now(UTC), "file_deleted": file_deleted, "last_error": None,
        }, synchronize_session=False)
        self._session.commit()

    def defer_deletion(self, document_id: str, error_code: str) -> None:
        self._session.query(DocumentDeletionModel).filter(DocumentDeletionModel.document_id == document_id).update({
            "attempts": DocumentDeletionModel.attempts + 1,
            "next_attempt_at": datetime.now(UTC) + timedelta(seconds=60),
            "last_error": error_code,
        }, synchronize_session=False)
        self._session.commit()

    def release_deletion(self) -> None:
        self._session.rollback()

    def pending_deletions(self) -> list[str]:
        return list(self._session.scalars(
            select(DocumentDeletionModel.document_id)
            .where(DocumentDeletionModel.completed_at.is_(None), DocumentDeletionModel.next_attempt_at <= func.now())
            .order_by(DocumentDeletionModel.next_attempt_at, DocumentDeletionModel.document_id).limit(20)
        ))

    def storage_paths(self):
        with self._session.execute(
            select(DocumentModel.storage_path).distinct(), execution_options={"yield_per": 100},
        ) as rows:
            yield from rows.scalars()

    def _to_deletion(self, deletion: DocumentDeletionModel) -> DocumentDeletion:
        return DocumentDeletion(
            document_id=deletion.document_id, filename=deletion.filename, storage_path=deletion.storage_path,
            completed_at=deletion.completed_at, file_deleted=bool(deletion.file_deleted),
        )

    def list_assigned_to_me(self) -> list[DocumentAssignmentModel]:
        return (
            self._session.query(DocumentAssignmentModel)
            .filter(DocumentAssignmentModel.assigned_to_user_id == user_id(self._current_user))
            .order_by(DocumentAssignmentModel.created_at.desc())
            .all()
        )

    def list_managed_by_me(self) -> list[DocumentAssignmentModel]:
        return (
            self._session.query(DocumentAssignmentModel)
            .filter(DocumentAssignmentModel.assigned_by_user_id == user_id(self._current_user))
            .order_by(DocumentAssignmentModel.created_at.desc())
            .all()
        )

    def create_assignment(
        self,
        document_id: str,
        assigned_to_user_id: str,
        allow_download: bool = True,
        due_at=None,
        metadata: dict | None = None,
    ) -> DocumentAssignmentModel | None:
        document = self._accessible_document_for_assignment(document_id)
        if document is None:
            return None

        tenant_id = document.tenant_id or (document.metadata_ or {}).get("tenant_id")
        if not tenant_id:
            return None

        existing = (
            self._session.query(DocumentAssignmentModel)
            .filter(
                DocumentAssignmentModel.document_id == document_id,
                DocumentAssignmentModel.assigned_to_user_id == assigned_to_user_id,
            )
            .first()
        )
        if existing is not None:
            existing.status = "PENDING"
            existing.rejection_reason = None
            existing.due_at = due_at
            existing.allow_download = allow_download
            existing.metadata_ = metadata or existing.metadata_ or {}
            self._session.commit()
            self._session.refresh(existing)
            self._record_assignment_event(existing, "ASSIGNED", metadata={"updated": True})
            self._notify_assignment(existing, title="Documento reasignado", body="Tienes un documento pendiente de revision.")
            self._audit("DOCUMENT_REASSIGNED", "document_assignment", existing.assignment_id, target_user_id=assigned_to_user_id)
            return existing

        assignment = DocumentAssignmentModel(
            document_id=document_id,
            tenant_id=str(tenant_id),
            assigned_to_user_id=assigned_to_user_id,
            assigned_by_user_id=user_id(self._current_user),
            assigned_by_role=self._current_user.get("active_role"),
            allow_download=allow_download,
            due_at=due_at,
            metadata_=metadata or {},
        )
        self._session.add(assignment)
        self._session.commit()
        self._session.refresh(assignment)
        self._record_assignment_event(assignment, "ASSIGNED")
        self._notify_assignment(assignment, title="Documento asignado", body="Tienes un documento pendiente de revision.")
        self._audit("DOCUMENT_ASSIGNED", "document_assignment", assignment.assignment_id, target_user_id=assigned_to_user_id)
        return assignment

    def update_assignment_status(
        self,
        assignment_id: str,
        status: str,
        reason: str | None = None,
        signature_value: str | None = None,
    ) -> DocumentAssignmentModel | None:
        assignment = (
            self._session.query(DocumentAssignmentModel)
            .filter(
                DocumentAssignmentModel.assignment_id == assignment_id,
                DocumentAssignmentModel.assigned_to_user_id == user_id(self._current_user),
            )
            .first()
        )
        if assignment is None:
            return None
        assignment.status = status
        if status == "REJECTED":
            assignment.rejection_reason = reason
        if status == "SIGNED":
            assignment.signature_value = signature_value
            assignment.signed_at = datetime.now(UTC)
        self._session.commit()
        self._session.refresh(assignment)
        self._record_assignment_event(assignment, status, reason=reason)
        self._notify_assignment_actor(assignment, status)
        self._audit(f"DOCUMENT_ASSIGNMENT_{status}", "document_assignment", assignment.assignment_id, target_user_id=assignment.assigned_by_user_id)
        return assignment

    def cancel_assignment(self, assignment_id: str, reason: str | None = None) -> DocumentAssignmentModel | None:
        assignment = self._managed_assignment(assignment_id)
        if assignment is None:
            return None
        assignment.status = "CANCELLED"
        assignment.rejection_reason = reason
        self._session.commit()
        self._session.refresh(assignment)
        self._record_assignment_event(assignment, "CANCELLED", reason=reason)
        self._notify_assignment(assignment, title="Asignacion cancelada", body="Una asignacion documental fue cancelada.")
        self._audit("DOCUMENT_ASSIGNMENT_CANCELLED", "document_assignment", assignment.assignment_id, target_user_id=assignment.assigned_to_user_id)
        return assignment

    def list_assignment_events(self, assignment_id: str) -> list[DocumentAssignmentEventModel]:
        assignment = self._visible_assignment(assignment_id)
        if assignment is None:
            return []
        return (
            self._session.query(DocumentAssignmentEventModel)
            .filter(DocumentAssignmentEventModel.assignment_id == assignment_id)
            .order_by(DocumentAssignmentEventModel.created_at.asc())
            .all()
        )

    def list_notifications(self, status: str | None = None, limit: int = 50) -> list[NotificationModel]:
        query = self._session.query(NotificationModel).filter(NotificationModel.recipient_user_id == user_id(self._current_user))
        if status:
            query = query.filter(NotificationModel.status == status)
        return query.order_by(NotificationModel.created_at.desc()).limit(limit).all()

    def mark_notification_read(self, notification_id: str) -> NotificationModel | None:
        notification = (
            self._session.query(NotificationModel)
            .filter(
                NotificationModel.notification_id == notification_id,
                NotificationModel.recipient_user_id == user_id(self._current_user),
            )
            .first()
        )
        if notification is None:
            return None
        notification.status = "READ"
        notification.read_at = datetime.now(UTC)
        self._session.commit()
        self._session.refresh(notification)
        return notification

    def can_download(self, document_id: str) -> bool:
        document = self._accessible_documents_query().filter(DocumentModel.document_id == document_id).first()
        if document is None:
            return False
        if is_superadmin_user(self._current_user):
            return True
        tenant_id = document.tenant_id if document.tenant_id is not None else (document.metadata_ or {}).get("tenant_id")
        if tenant_id and str(tenant_id) in tenant_ids_for_role(self._current_user, "TENANT_ADMIN"):
            return True
        current_user_id = user_id(self._current_user)
        owner_id = document.owner_user_id if document.owner_user_id is not None else (document.metadata_ or {}).get("owner_user_id")
        if str(owner_id) == current_user_id:
            return bool(document.allow_download)
        assignment = (
            self._session.query(DocumentAssignmentModel)
            .filter(
                DocumentAssignmentModel.document_id == document_id,
                DocumentAssignmentModel.assigned_to_user_id == current_user_id,
            )
            .first()
        )
        return bool(assignment and assignment.allow_download and assignment.status not in ("CANCELLED", "EXPIRED"))

    def record_document_event(self, document_id: str, action: str, metadata: dict | None = None) -> None:
        document = self._session.get(DocumentModel, document_id)
        self._audit(action, "document", document_id, tenant_id=document.tenant_id if document else None, metadata=metadata)

    def _accessible_documents_query(self):
        return self._apply_access_filter(self._session.query(DocumentModel))

    def _apply_access_filter(self, statement):
        if is_superadmin_user(self._current_user):
            return statement

        current_user_id = user_id(self._current_user)
        assignment = DocumentAssignmentModel
        active_assignment = select(1).where(
            assignment.document_id == DocumentModel.document_id,
            assignment.status.not_in(("CANCELLED", "EXPIRED")),
            or_(
                assignment.assigned_to_user_id == current_user_id,
                assignment.assigned_by_user_id == current_user_id,
            ),
        ).exists()
        owner_id = func.coalesce(DocumentModel.owner_user_id, DocumentModel.metadata_["owner_user_id"].astext)
        tenant_id = func.coalesce(DocumentModel.tenant_id, DocumentModel.metadata_["tenant_id"].astext)
        clauses = [owner_id == current_user_id, active_assignment]
        admin_tenant_ids = tenant_ids_for_role(self._current_user, "TENANT_ADMIN")
        if admin_tenant_ids:
            clauses.append(tenant_id.in_(admin_tenant_ids))
        groups = user_groups(self._current_user)
        if groups:
            member_tenant_ids = [
                str(membership["tenant_id"])
                for membership in tenant_memberships(self._current_user)
                if membership.get("tenant_id")
            ]
            clauses.append(
                or_(tenant_id.is_(None), tenant_id.in_(member_tenant_ids))
                & or_(*(DocumentModel.metadata_.contains({"owner_groups": [group]}) for group in groups))
            )
        return statement.filter(or_(*clauses))

    def _accessible_document_for_assignment(self, document_id: str) -> DocumentModel | None:
        document = self._accessible_documents_query().filter(DocumentModel.document_id == document_id).first()
        if document is None:
            return None
        if is_superadmin_user(self._current_user):
            return document
        if self._current_user.get("active_role") in ("TENANT_ADMIN", "LEADER"):
            return document
        return None

    def _visible_assignment(self, assignment_id: str) -> DocumentAssignmentModel | None:
        assignment = self._session.get(DocumentAssignmentModel, assignment_id)
        if assignment is None:
            return None
        if is_superadmin_user(self._current_user):
            return assignment
        current_user_id = user_id(self._current_user)
        if assignment.assigned_to_user_id == current_user_id or assignment.assigned_by_user_id == current_user_id:
            return assignment
        if assignment.tenant_id in tenant_ids_for_role(self._current_user, "TENANT_ADMIN"):
            return assignment
        return None

    def _managed_assignment(self, assignment_id: str) -> DocumentAssignmentModel | None:
        assignment = self._visible_assignment(assignment_id)
        if assignment is None:
            return None
        if is_superadmin_user(self._current_user):
            return assignment
        if assignment.assigned_by_user_id == user_id(self._current_user):
            return assignment
        if assignment.tenant_id in tenant_ids_for_role(self._current_user, "TENANT_ADMIN"):
            return assignment
        return None

    def _record_assignment_event(
        self,
        assignment: DocumentAssignmentModel,
        action: str,
        reason: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        self._session.add(
            DocumentAssignmentEventModel(
                assignment_id=assignment.assignment_id,
                actor_user_id=user_id(self._current_user),
                action=action,
                reason=reason,
                metadata_=metadata or {},
            )
        )
        self._session.commit()

    def _notify_assignment(self, assignment: DocumentAssignmentModel, title: str, body: str) -> None:
        self._session.add(
            NotificationModel(
                tenant_id=assignment.tenant_id,
                recipient_user_id=assignment.assigned_to_user_id,
                actor_user_id=user_id(self._current_user),
                document_id=assignment.document_id,
                assignment_id=assignment.assignment_id,
                type="DOCUMENT_ASSIGNMENT",
                title=title,
                body=body,
            )
        )
        self._session.commit()

    def _notify_assignment_actor(self, assignment: DocumentAssignmentModel, status: str) -> None:
        self._session.add(
            NotificationModel(
                tenant_id=assignment.tenant_id,
                recipient_user_id=assignment.assigned_by_user_id,
                actor_user_id=user_id(self._current_user),
                document_id=assignment.document_id,
                assignment_id=assignment.assignment_id,
                type=f"DOCUMENT_ASSIGNMENT_{status}",
                title="Actualizacion de documento",
                body=f"La asignacion cambio a estado {status}.",
            )
        )
        self._session.commit()

    def _audit(
        self,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        target_user_id: str | None = None,
        tenant_id: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        self._session.add(
            AuditLogModel(
                tenant_id=tenant_id or self._current_user.get("active_tenant_id"),
                actor_user_id=user_id(self._current_user),
                action=action,
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id else None,
                target_user_id=target_user_id,
                metadata_=metadata or {},
            )
        )
        self._session.commit()

    def _to_file(self, document: DocumentModel) -> DocumentFile:
        return DocumentFile(
            document_id=str(document.document_id),
            filename=document.filename,
            mime_type=document.mime_type,
            status=document.status,
            storage_path=document.storage_path,
            metadata=document.metadata_ or {},
            allow_download=document.allow_download,
            processing_error=document.processing_error,
            processed_at=document.processed_at,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )
