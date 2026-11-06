from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config.security import is_superadmin_user, tenant_ids_for_role, tenant_memberships, user_groups, user_id
from app.infrastructure.database.models import DocumentAssignmentModel, DocumentModel, TransferEventModel
from app.shared.errors import NotFoundError


class TransferRepositoryPg:
    def __init__(self, session: Session, current_user: dict) -> None:
        self._session = session
        self._current_user = current_user
        self._owner_user_id = user_id(current_user)

    def list(self, limit: int = 50) -> list[TransferEventModel]:
        return (
            self._session.query(TransferEventModel)
            .filter(TransferEventModel.owner_user_id == self._owner_user_id)
            .order_by(TransferEventModel.created_at.desc())
            .limit(limit)
            .all()
        )

    def create(self, payload: dict) -> TransferEventModel:
        try:
            if payload.get("document_id") is not None:
                self._require_document_reference(payload["document_id"])
            transfer = TransferEventModel(owner_user_id=self._owner_user_id, **payload)
            self._session.add(transfer)
            self._session.commit()
            self._session.refresh(transfer)
            return transfer
        except Exception:
            self._session.rollback()
            raise

    def update(self, transfer_id: str, payload: dict) -> TransferEventModel | None:
        try:
            transfer = self._get(transfer_id)
            if transfer is None:
                return None
            if payload.get("document_id") is not None:
                self._require_document_reference(payload["document_id"])
            for key, value in payload.items():
                setattr(transfer, key, value)
            self._session.commit()
            self._session.refresh(transfer)
            return transfer
        except Exception:
            self._session.rollback()
            raise

    def clear_history(self) -> int:
        try:
            rows = (
                self._session.query(TransferEventModel)
                .filter(
                    TransferEventModel.owner_user_id == self._owner_user_id,
                    TransferEventModel.status.in_(["COMPLETED", "FAILED", "CANCELLED"]),
                )
                .all()
            )
            count = len(rows)
            for row in rows:
                self._session.delete(row)
            self._session.commit()
            return count
        except Exception:
            self._session.rollback()
            raise

    def _get(self, transfer_id: str) -> TransferEventModel | None:
        return (
            self._session.query(TransferEventModel)
            .filter(TransferEventModel.transfer_id == transfer_id, TransferEventModel.owner_user_id == self._owner_user_id)
            .first()
        )


    def _require_document_reference(self, document_id: str) -> None:
        # Hold the reference until commit: a concurrent DELETE must wait, then SET NULL.
        # This requires a narrowly scoped lock helper when runtime is restricted (TRANSFER-007).
        identifier = self._session.scalar(select(DocumentModel.document_id).where(
            DocumentModel.document_id == document_id,
        ).with_for_update(read=True, key_share=True))
        if identifier is None or not self._accessible_documents().filter(DocumentModel.document_id == document_id).first():
            raise NotFoundError("Document not found.")

    def _accessible_documents(self):
        statement = self._session.query(DocumentModel.document_id)
        if is_superadmin_user(self._current_user):
            return statement
        assignment = DocumentAssignmentModel
        active_assignment = select(1).where(
            assignment.document_id == DocumentModel.document_id,
            assignment.status.not_in(("CANCELLED", "EXPIRED")),
            or_(assignment.assigned_to_user_id == self._owner_user_id,
                assignment.assigned_by_user_id == self._owner_user_id),
        ).exists()
        owner = func.coalesce(DocumentModel.owner_user_id, DocumentModel.metadata_["owner_user_id"].astext)
        tenant = func.coalesce(DocumentModel.tenant_id, DocumentModel.metadata_["tenant_id"].astext)
        clauses = [owner == self._owner_user_id, active_assignment]
        admin_tenants = tenant_ids_for_role(self._current_user, "TENANT_ADMIN")
        if admin_tenants:
            clauses.append(tenant.in_(admin_tenants))
        groups = user_groups(self._current_user)
        if groups:
            member_tenants = [str(membership["tenant_id"]) for membership in tenant_memberships(self._current_user)
                              if membership.get("tenant_id")]
            clauses.append(or_(tenant.is_(None), tenant.in_(member_tenants))
                           & or_(*(DocumentModel.metadata_.contains({"owner_groups": [group]}) for group in groups)))
        return statement.filter(or_(*clauses))
