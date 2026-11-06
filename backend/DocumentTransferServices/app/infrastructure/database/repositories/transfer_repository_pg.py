from __future__ import annotations

from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.orm import Session

from app.config.security import is_superadmin_user, tenant_ids_for_role, tenant_memberships, user_groups, user_id
from app.domain.transfer_state import TERMINAL_STATES, validate_initial_state, validate_transition
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
            validate_initial_state(payload)
            self._lock_owner()
            if payload.get("document_id") is not None:
                self._require_document_reference(payload["document_id"])
            transfer = TransferEventModel(owner_user_id=self._owner_user_id, **payload)
            self._session.add(transfer)
            return self._commit_transfer(transfer)
        except Exception:
            self._session.rollback()
            raise

    def update(self, transfer_id: str, payload: dict) -> TransferEventModel | None:
        try:
            self._lock_owner()
            transfer = self._get(transfer_id)
            if transfer is None:
                self._session.rollback()
                return None
            # Documents before event rows: DELETE documents locks in that order for SET NULL.
            if payload.get("document_id") is not None:
                self._require_document_reference(payload["document_id"])
            transfer = self._get(transfer_id, lock=True)
            if transfer is None:
                self._session.rollback()
                return None
            validate_transition(transfer, payload)
            for key, value in payload.items():
                setattr(transfer, key, value)
            return self._commit_transfer(transfer)
        except Exception:
            self._session.rollback()
            raise

    def clear_history(self) -> int:
        try:
            self._lock_owner()
            # One bounded batch, with deterministic ordering and no Python row materialization.
            candidates = select(TransferEventModel.transfer_id).where(
                TransferEventModel.owner_user_id == self._owner_user_id,
                TransferEventModel.status.in_(TERMINAL_STATES),
            ).order_by(TransferEventModel.created_at, TransferEventModel.transfer_id).limit(1000)
            result = self._session.execute(delete(TransferEventModel).where(
                TransferEventModel.owner_user_id == self._owner_user_id,
                TransferEventModel.status.in_(TERMINAL_STATES),
                TransferEventModel.transfer_id.in_(candidates),
            ).execution_options(synchronize_session=False))
            count = result.rowcount
            self._session.commit()
            return count
        except Exception:
            self._session.rollback()
            raise

    def _lock_owner(self) -> None:
        self._session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended('blandskron.transfer.owner:' || :owner, 0))"),
                              {"owner": self._owner_user_id})

    def _commit_transfer(self, transfer: TransferEventModel) -> TransferEventModel:
        # Snapshot while locks are held. A cleanup immediately after commit must not
        # turn a successful write into an ORM refresh/expired-instance error.
        self._session.flush()
        self._session.refresh(transfer)
        self._session.expunge(transfer)
        self._session.commit()
        return transfer

    def _get(self, transfer_id: str, *, lock: bool = False) -> TransferEventModel | None:
        query = self._session.query(TransferEventModel).populate_existing().filter(
            TransferEventModel.transfer_id == transfer_id, TransferEventModel.owner_user_id == self._owner_user_id,
        )
        if lock:
            query = query.with_for_update()
        return query.first()


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
