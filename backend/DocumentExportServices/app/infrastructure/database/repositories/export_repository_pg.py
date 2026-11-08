from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session, undefer

from app.config.security import ExportUser
from app.shared.errors import NotFoundError
from app.infrastructure.database.models import DocumentExportModel


class ExportRepositoryPg:
    def __init__(self, session: Session, current_user: ExportUser) -> None:
        self._session = session
        self._owner_user_id = current_user.user_id

    def validate_references(self, conversation_id: str | None, message_id: str | None) -> None:
        # Hold reference rows until the export transaction ends, before any rendering.
        if conversation_id is not None:
            own = self._session.scalar(text("""
                SELECT conversation_id FROM public.conversations
                WHERE conversation_id=:conversation AND owner_user_id=:owner FOR SHARE
            """), {"conversation": conversation_id, "owner": self._owner_user_id})
            if own is None:
                raise NotFoundError("Export reference not found.")
        if message_id is not None:
            own = self._session.scalar(text("""
                SELECT m.message_id FROM public.conversation_messages AS m
                JOIN public.conversations AS c ON c.conversation_id=m.conversation_id
                WHERE m.message_id=:message AND m.owner_user_id=:owner AND c.owner_user_id=:owner
                  AND (CAST(:conversation AS TEXT) IS NULL OR m.conversation_id=:conversation)
                FOR SHARE OF c,m
            """), {"message": message_id, "owner": self._owner_user_id, "conversation": conversation_id})
            if own is None:
                raise NotFoundError("Export reference not found.")

    def lock_owner(self):
        self._session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended('blandskron.export:' || :owner,0))"), {"owner": self._owner_user_id})

    def operation(self, key):
        if key is None:
            return None
        return self._session.query(DocumentExportModel).filter_by(owner_user_id=self._owner_user_id, operation_key=key).first()

    def check_capacity(self, size):
        from app.config.export_limits import GLOBAL_BYTES, OWNER_BYTES, OWNER_COUNT
        from app.shared.errors import ExportConflictError
        self._session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended('blandskron.export.capacity',0))"))
        row = self._session.execute(text("""
            SELECT count(*) FILTER (WHERE owner_user_id=:owner),
                   coalesce(sum(greatest(file_size_bytes,0)) FILTER (WHERE owner_user_id=:owner),0),
                   coalesce(sum(octet_length(pdf_data)),0) FROM document_exports
        """), {"owner": self._owner_user_id}).one()
        if row[0] >= OWNER_COUNT or row[1] + size > OWNER_BYTES or row[2] + size > GLOBAL_BYTES:
            raise ExportConflictError("Export quota reached.")

    def create_export(self, **values):
        export = DocumentExportModel(owner_user_id=self._owner_user_id, format="PDF", status="COMPLETED",
                                     mime_type="application/pdf", storage_path="", **values)
        self._session.add(export)
        self._session.commit()
        self._session.refresh(export)
        return export

    def delete_export(self, export_id):
        self.lock_owner()
        export = self.get_export(export_id)
        if export is None:
            raise NotFoundError("Export not found.")
        self._session.delete(export)
        self._session.commit()

    def get_export(self, export_id: str) -> DocumentExportModel | None:
        return (
            self._session.query(DocumentExportModel)
            .filter(
                DocumentExportModel.export_id == export_id,
                DocumentExportModel.owner_user_id == self._owner_user_id,
            )
            .first()
        )

    def get_export_for_download(self, export_id):
        return (self._session.query(DocumentExportModel).options(undefer(DocumentExportModel.pdf_data))
                .filter(DocumentExportModel.export_id == export_id, DocumentExportModel.owner_user_id == self._owner_user_id)
                .with_for_update(read=True).first())

    def list_exports(self, source_type: str | None = None) -> list[DocumentExportModel]:
        statement = self._session.query(DocumentExportModel).filter(DocumentExportModel.owner_user_id == self._owner_user_id)
        if source_type:
            statement = statement.filter(DocumentExportModel.source_type == source_type)
        return statement.order_by(DocumentExportModel.created_at.desc()).all()

