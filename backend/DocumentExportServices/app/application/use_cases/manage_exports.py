from __future__ import annotations

from pathlib import Path
from re import sub
from uuid import uuid4

from app.domain.entities import ChatPdfExport
from app.shared.errors import NotFoundError, ValidationError


class ManageExports:
    def __init__(self, repository, renderer, storage_base_path: str) -> None:
        self._repository = repository
        self._renderer = renderer
        self._storage_base_path = Path(storage_base_path)

    def create_chat_pdf_export(self, payload):
        title = (payload.title or "Respuesta documental").strip()
        if not payload.answer.strip():
            raise ValidationError("La respuesta del chat es obligatoria para exportar.")

        self._repository.validate_references(payload.conversation_id, payload.message_id)

        export_source_id = payload.message_id or payload.conversation_id
        filename = f"{self._slug(title)}_{uuid4().hex[:10]}.pdf"
        output_path = (self._storage_base_path / filename).resolve()
        safe_base = self._storage_base_path.resolve()
        if safe_base not in output_path.parents and output_path != safe_base:
            raise ValidationError("Ruta de exportacion invalida.")

        chat_export = ChatPdfExport(
            title=title,
            question=payload.question,
            answer=payload.answer,
            sources=payload.sources,
            conversation_id=payload.conversation_id,
            message_id=payload.message_id,
            metadata=payload.metadata,
        )
        self._renderer.render(chat_export, output_path)

        return self._repository.create_export(
            source_type="chat_message",
            source_id=export_source_id,
            conversation_id=payload.conversation_id,
            message_id=payload.message_id,
            title=title,
            filename=filename,
            storage_path=str(output_path),
            file_size_bytes=output_path.stat().st_size,
            metadata={
                **(payload.metadata or {}),
                "question": payload.question,
                "source_count": len(payload.sources or []),
            },
        )

    def get_export(self, export_id: str):
        export = self._repository.get_export(export_id)
        if export is None:
            raise NotFoundError("Export not found.")
        return export

    def list_exports(self, source_type: str | None = None):
        return self._repository.list_exports(source_type)

    def download_path(self, export_id: str) -> Path:
        export = self.get_export(export_id)
        path = Path(export.storage_path)
        if not path.exists():
            raise NotFoundError("Export file not found.")
        return path

    def _slug(self, value: str) -> str:
        normalized = sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
        return normalized[:56] or "export"

