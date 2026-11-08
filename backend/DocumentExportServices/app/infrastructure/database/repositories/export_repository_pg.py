from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

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

    def create_export(
        self,
        *,
        source_type: str,
        source_id: str | None,
        conversation_id: str | None,
        message_id: str | None,
        title: str,
        filename: str,
        storage_path: str,
        file_size_bytes: int,
        metadata: dict,
    ) -> DocumentExportModel:
        export = DocumentExportModel(
            owner_user_id=self._owner_user_id,
            source_type=source_type,
            source_id=source_id,
            conversation_id=conversation_id,
            message_id=message_id,
            title=title,
            format="PDF",
            status="COMPLETED",
            filename=filename,
            storage_path=storage_path,
            mime_type="application/pdf",
            file_size_bytes=file_size_bytes,
            metadata_=metadata,
        )
        self._session.add(export)
        self._session.commit()
        self._session.refresh(export)
        return export

    def get_export(self, export_id: str) -> DocumentExportModel | None:
        return (
            self._session.query(DocumentExportModel)
            .filter(
                DocumentExportModel.export_id == export_id,
                DocumentExportModel.owner_user_id == self._owner_user_id,
            )
            .first()
        )

    def list_exports(self, source_type: str | None = None) -> list[DocumentExportModel]:
        statement = self._session.query(DocumentExportModel).filter(DocumentExportModel.owner_user_id == self._owner_user_id)
        if source_type:
            statement = statement.filter(DocumentExportModel.source_type == source_type)
        return statement.order_by(DocumentExportModel.created_at.desc()).all()

