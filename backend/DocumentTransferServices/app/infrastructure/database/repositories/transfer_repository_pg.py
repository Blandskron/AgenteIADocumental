from __future__ import annotations

from sqlalchemy.orm import Session

from app.infrastructure.database.models import TransferEventModel


class TransferRepositoryPg:
    def __init__(self, session: Session, current_user: dict) -> None:
        self._session = session
        self._owner_user_id = _owner_user_id(current_user)

    def list(self, limit: int = 50) -> list[TransferEventModel]:
        return (
            self._session.query(TransferEventModel)
            .filter(TransferEventModel.owner_user_id == self._owner_user_id)
            .order_by(TransferEventModel.created_at.desc())
            .limit(limit)
            .all()
        )

    def create(self, payload: dict) -> TransferEventModel:
        transfer = TransferEventModel(owner_user_id=self._owner_user_id, **payload)
        self._session.add(transfer)
        self._session.commit()
        self._session.refresh(transfer)
        return transfer

    def update(self, transfer_id: str, payload: dict) -> TransferEventModel | None:
        transfer = self._get(transfer_id)
        if transfer is None:
            return None
        for key, value in payload.items():
            if value is not None:
                setattr(transfer, key, value)
        self._session.commit()
        self._session.refresh(transfer)
        return transfer

    def clear_history(self) -> int:
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

    def _get(self, transfer_id: str) -> TransferEventModel | None:
        return (
            self._session.query(TransferEventModel)
            .filter(TransferEventModel.transfer_id == transfer_id, TransferEventModel.owner_user_id == self._owner_user_id)
            .first()
        )


def _owner_user_id(current_user: dict) -> str:
    return str(current_user.get("user_id") or current_user.get("sub") or current_user.get("username") or "unknown")
