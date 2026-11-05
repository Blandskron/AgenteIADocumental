from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from app.config.security import is_superadmin_user, tenant_ids_for_role, tenant_memberships, user_groups, user_id
from app.domain.documents import DocumentContent, DocumentDeletion, DocumentFile
from app.shared.constants import MAX_CONTENT_CHARACTERS
from app.shared.errors import ConflictError, PayloadTooLarge, ValidationError
from app.infrastructure.database.models import (
    AuditLogModel,
    AuthUserModel,
    DocumentAssignmentEventModel,
    DocumentAssignmentModel,
    DocumentDeletionModel,
    DocumentEmbeddingModel,
    DocumentModel,
    NotificationModel,
    TenantMembershipModel,
    TenantModel,
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

    def list_assigned_to_me(self, limit: int = 50, offset: int = 0) -> list[DocumentAssignmentModel]:
        return (
            self._session.query(DocumentAssignmentModel)
            .filter(DocumentAssignmentModel.assigned_to_user_id == user_id(self._current_user))
            .order_by(DocumentAssignmentModel.created_at.desc(), DocumentAssignmentModel.assignment_id.desc())
            .limit(limit).offset(offset)
            .all()
        )

    def list_managed_by_me(self, limit: int = 50, offset: int = 0) -> list[DocumentAssignmentModel]:
        return (
            self._session.query(DocumentAssignmentModel)
            .filter(DocumentAssignmentModel.assigned_by_user_id == user_id(self._current_user))
            .order_by(DocumentAssignmentModel.created_at.desc(), DocumentAssignmentModel.assignment_id.desc())
            .limit(limit).offset(offset)
            .all()
        )

    def create_assignment(
        self,
        document_id: str,
        assigned_to_user_id: str,
        allow_download: bool = True,
        due_at: datetime | None = None,
        metadata: dict | None = None,
    ) -> DocumentAssignmentModel | None:
        with self._assignment_transaction():
            document = self._lock_assignment_document(document_id)
            if document is None:
                return None
            role = self._assignment_role(document)
            if role not in ("SUPERADMIN", "TENANT_ADMIN", "LEADER"):
                return None
            if role == "LEADER" and self._apply_access_filter(
                self._session.query(DocumentModel).filter(DocumentModel.document_id == document_id), allow_admin=False,
            ).first() is None:
                return None
            tenant_id = self._document_tenant(document)
            if self._active_user(assigned_to_user_id) is None or self._active_membership(tenant_id, assigned_to_user_id) is None:
                raise ValidationError("Recipient must be an active member of the document tenant.")
            if due_at is not None and due_at.tzinfo is None:
                due_at = due_at.replace(tzinfo=UTC)

            assignment = self._session.query(DocumentAssignmentModel).filter(
                DocumentAssignmentModel.document_id == document_id,
                DocumentAssignmentModel.assigned_to_user_id == assigned_to_user_id,
            ).with_for_update().populate_existing().first()
            reassigned = assignment is not None
            if reassigned:
                if assignment.tenant_id != tenant_id:
                    return None
                if assignment.assigned_by_user_id != user_id(self._current_user) and role not in ("SUPERADMIN", "TENANT_ADMIN"):
                    return None
                effective_metadata = metadata or assignment.metadata_ or {}
                if (
                    assignment.status == "PENDING"
                    and assignment.assigned_by_user_id == user_id(self._current_user)
                    and assignment.allow_download == allow_download
                    and assignment.due_at == due_at
                    and assignment.metadata_ == effective_metadata
                ):
                    return assignment
                assignment.status = "PENDING"
                assignment.rejection_reason = None
                assignment.signature_value = None
                assignment.signed_at = None
                assignment.metadata_ = effective_metadata
            else:
                assignment = DocumentAssignmentModel(
                    document_id=document_id, tenant_id=tenant_id, assigned_to_user_id=assigned_to_user_id,
                    metadata_=metadata or {},
                )
                self._session.add(assignment)
            assignment.assigned_by_user_id = user_id(self._current_user)
            assignment.assigned_by_role = role
            assignment.allow_download = allow_download
            assignment.due_at = due_at
            self._session.flush()
            self._record_assignment_event(assignment, "ASSIGNED", metadata={"updated": reassigned})
            self._notify_assignment(assignment, title="Documento asignado", body="Tienes un documento pendiente de revision.")
            self._audit(
                "DOCUMENT_REASSIGNED" if reassigned else "DOCUMENT_ASSIGNED",
                "document_assignment", assignment.assignment_id,
                target_user_id=assigned_to_user_id, tenant_id=tenant_id,
            )
            return assignment

    def update_assignment_status(
        self,
        assignment_id: str,
        status: str,
        reason: str | None = None,
        signature_value: str | None = None,
    ) -> DocumentAssignmentModel | None:
        transitions = {
            "ACCEPTED": {"PENDING", "VIEWED"},
            "REJECTED": {"PENDING", "VIEWED"},
            "SIGNED": {"PENDING", "VIEWED", "ACCEPTED"},
        }
        with self._assignment_transaction():
            locked = self._lock_assignment(assignment_id)
            if locked is None:
                return None
            assignment, document = locked
            if assignment.assigned_to_user_id != user_id(self._current_user) or self._assignment_role(
                document, require_membership=True,
            ) is None:
                return None
            if status not in transitions:
                raise ValidationError("Unsupported assignment action.")
            if status == "REJECTED" and (not reason or not reason.strip()):
                raise ValidationError("A rejection reason is required.")
            if status == "SIGNED" and (not signature_value or not signature_value.strip()):
                raise ValidationError("A signature value is required.")
            if assignment.status == status:
                if status == "SIGNED" and assignment.signature_value != signature_value:
                    raise ConflictError("Assignment already has a different signature.")
                if status == "REJECTED" and assignment.rejection_reason != reason:
                    raise ConflictError("Assignment already has a different rejection reason.")
                return assignment
            if assignment.status not in transitions[status]:
                raise ConflictError("Assignment transition is not allowed from its current state.")
            assignment.status = status
            if status == "REJECTED":
                assignment.rejection_reason = reason
            if status == "SIGNED":
                assignment.signature_value = signature_value
                assignment.signed_at = datetime.now(UTC)
            self._record_assignment_event(assignment, status, reason=reason)
            self._notify_assignment_actor(assignment, status)
            self._audit(
                f"DOCUMENT_ASSIGNMENT_{status}", "document_assignment", assignment.assignment_id,
                target_user_id=assignment.assigned_by_user_id, tenant_id=assignment.tenant_id,
            )
            return assignment

    def cancel_assignment(self, assignment_id: str, reason: str | None = None) -> DocumentAssignmentModel | None:
        with self._assignment_transaction():
            locked = self._lock_assignment(assignment_id)
            if locked is None:
                return None
            assignment, document = locked
            role = self._assignment_role(document)
            if role is None or (
                assignment.assigned_by_user_id != user_id(self._current_user) and role not in ("SUPERADMIN", "TENANT_ADMIN")
            ):
                return None
            if assignment.status == "CANCELLED":
                if assignment.rejection_reason != reason:
                    raise ConflictError("Assignment was cancelled with a different reason.")
                return assignment
            if assignment.status == "EXPIRED":
                raise ConflictError("Expired assignment cannot be cancelled.")
            assignment.status = "CANCELLED"
            assignment.rejection_reason = reason
            self._record_assignment_event(assignment, "CANCELLED", reason=reason)
            self._notify_assignment(assignment, title="Asignacion cancelada", body="Una asignacion documental fue cancelada.")
            self._audit(
                "DOCUMENT_ASSIGNMENT_CANCELLED", "document_assignment", assignment.assignment_id,
                target_user_id=assignment.assigned_to_user_id, tenant_id=assignment.tenant_id,
            )
            return assignment

    def list_assignment_events(self, assignment_id: str, limit: int = 50, offset: int = 0) -> list[DocumentAssignmentEventModel] | None:
        assignment = self._visible_assignment(assignment_id)
        if assignment is None:
            return None
        return (
            self._session.query(DocumentAssignmentEventModel)
            .filter(DocumentAssignmentEventModel.assignment_id == assignment_id)
            .order_by(DocumentAssignmentEventModel.created_at.asc(), DocumentAssignmentEventModel.event_id.asc())
            .limit(limit).offset(offset)
            .all()
        )

    def list_notifications(self, status: str | None = None, limit: int = 50, offset: int = 0) -> list[NotificationModel]:
        query = self._session.query(NotificationModel).filter(NotificationModel.recipient_user_id == user_id(self._current_user))
        if status:
            query = query.filter(NotificationModel.status == status)
        return query.order_by(NotificationModel.created_at.desc(), NotificationModel.notification_id.desc()).limit(limit).offset(offset).all()

    def mark_notification_read(self, notification_id: str) -> NotificationModel | None:
        with self._assignment_transaction():
            if self._active_user(user_id(self._current_user)) is None:
                return None
            notification = self._session.query(NotificationModel).filter(
                NotificationModel.notification_id == notification_id,
                NotificationModel.recipient_user_id == user_id(self._current_user),
            ).with_for_update().populate_existing().first()
            if notification is None:
                return None
            if notification.status != "READ":
                notification.status = "READ"
                notification.read_at = datetime.now(UTC)
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
        self._audit(action, "document", document_id, tenant_id=self._document_tenant(document) if document else None, metadata=metadata)
        self._session.commit()

    def _accessible_documents_query(self):
        return self._apply_access_filter(self._session.query(DocumentModel))

    def _apply_access_filter(self, statement, allow_admin: bool = True):
        if allow_admin and is_superadmin_user(self._current_user):
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
        if allow_admin and admin_tenant_ids:
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

    @contextmanager
    def _assignment_transaction(self):
        try:
            yield
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

    def _lock_assignment_document(self, document_id: str) -> DocumentModel | None:
        return self._session.query(DocumentModel).filter(
            DocumentModel.document_id == document_id,
        ).with_for_update().populate_existing().first()

    def _document_tenant(self, document: DocumentModel) -> str | None:
        tenant_id = document.tenant_id if document.tenant_id is not None else (document.metadata_ or {}).get("tenant_id")
        return str(tenant_id) if tenant_id is not None else None

    def _active_user(self, identifier: str) -> AuthUserModel | None:
        try:
            numeric_id = int(identifier)
        except (TypeError, ValueError):
            return None
        if str(numeric_id) != identifier or not 0 < numeric_id <= 2**63 - 1:
            return None
        return self._session.query(AuthUserModel).from_statement(
            text("SELECT * FROM public.access_active_user(:identifier)"),
        ).params(identifier=numeric_id).populate_existing().first()

    def _active_membership(self, tenant_id: str, identifier: str) -> TenantMembershipModel | None:
        return self._session.query(TenantMembershipModel).from_statement(
            text("SELECT * FROM public.access_active_membership(:tenant, :identifier)"),
        ).params(tenant=tenant_id, identifier=identifier).populate_existing().first()

    def _assignment_role(self, document: DocumentModel, require_membership: bool = False) -> str | None:
        tenant_id = self._document_tenant(document)
        tenant = self._session.query(TenantModel).from_statement(
            text("SELECT * FROM public.access_active_tenant(:identifier)"),
        ).params(identifier=tenant_id).populate_existing().first()
        actor = self._active_user(user_id(self._current_user))
        if tenant is None or actor is None:
            return None
        if actor.is_superuser and not require_membership:
            return "SUPERADMIN"
        membership = self._active_membership(tenant_id, user_id(self._current_user))
        return membership.role if membership is not None else None

    def _lock_assignment(self, assignment_id: str) -> tuple[DocumentAssignmentModel, DocumentModel] | None:
        document_id = self._session.scalar(select(DocumentAssignmentModel.document_id).where(
            DocumentAssignmentModel.assignment_id == assignment_id,
        ))
        if document_id is None:
            return None
        document = self._lock_assignment_document(document_id)
        if document is None:
            return None
        assignment = self._session.query(DocumentAssignmentModel).filter(
            DocumentAssignmentModel.assignment_id == assignment_id,
        ).with_for_update().populate_existing().first()
        if assignment is None or assignment.tenant_id != self._document_tenant(document):
            return None
        return assignment, document

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
                created_at=datetime.now(UTC),
            )
        )

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
                created_at=datetime.now(UTC),
            )
        )

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
                created_at=datetime.now(UTC),
            )
        )

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
                tenant_id=tenant_id,
                actor_user_id=user_id(self._current_user),
                action=action,
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id else None,
                target_user_id=target_user_id,
                metadata_=metadata or {},
                created_at=datetime.now(UTC),
            )
        )

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
