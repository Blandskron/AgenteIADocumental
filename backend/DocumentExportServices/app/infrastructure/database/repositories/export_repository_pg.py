from __future__ import annotations

from sqlalchemy.orm import Session

from app.config.security import owner_user_id
from app.infrastructure.database.models import DocumentExportModel


class ExportRepositoryPg:
    def __init__(self, session: Session, current_user: dict) -> None:
        self._session = session
        self._owner_user_id = owner_user_id(current_user)

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

