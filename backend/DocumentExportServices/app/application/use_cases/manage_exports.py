from datetime import UTC, datetime, timedelta
from hashlib import sha256
from re import sub
from uuid import uuid4

from app.config.export_limits import MAX_PDF, RETENTION_DAYS
from app.domain.entities import ChatPdfExport
from app.shared.errors import ExportConflictError, ExportExpiredError, ExportGenerationError, NotFoundError


def export_status(export):
    if export.pdf_sha256 is None:
        return "MIGRATION_REQUIRED"
    if export.expires_at is not None and export.expires_at <= datetime.now(UTC):
        return "EXPIRED"
    return export.status


class ManageExports:
    def __init__(self, repository, renderer):
        self._repository = repository
        self._renderer = renderer

    def create_chat_pdf_export(self, payload, operation_key=None):
        self._repository.lock_owner()
        # Stable semantic ordering also for metadata keys.
        import json
        digest = sha256(json.dumps(payload.model_dump(), sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
        previous = self._repository.operation(operation_key)
        if previous is not None:
            if previous.request_sha256 != digest or export_status(previous) != "COMPLETED":
                raise ExportConflictError("Idempotency key conflicts with operation.")
            return previous
        self._repository.validate_references(payload.conversation_id, payload.message_id)
        sources = [source.model_dump() for source in payload.sources]
        export = ChatPdfExport(title=payload.title, question=payload.question, answer=payload.answer,
                               sources=sources, conversation_id=payload.conversation_id,
                               message_id=payload.message_id, metadata=payload.metadata)
        content = self._renderer.render(export)
        if not content.startswith(b"%PDF-") or not 0 < len(content) <= MAX_PDF:
            raise ExportGenerationError("Invalid generated PDF.")
        self._repository.check_capacity(len(content))
        return self._repository.create_export(
            source_type="chat_message", source_id=payload.message_id or payload.conversation_id,
            conversation_id=payload.conversation_id, message_id=payload.message_id, title=payload.title,
            filename=f"{self._slug(payload.title)}_{uuid4().hex[:10]}.pdf", file_size_bytes=len(content),
            pdf_data=content, pdf_sha256=sha256(content).hexdigest(),
            expires_at=datetime.now(UTC) + timedelta(days=RETENTION_DAYS), operation_key=operation_key,
            request_sha256=digest, metadata_={**payload.metadata, "question": payload.question, "source_count": len(sources)},
        )

    def get_export(self, export_id):
        export = self._repository.get_export(export_id)
        if export is None:
            raise NotFoundError("Export not found.")
        return export

    def list_exports(self, source_type=None, limit=20, before=None):
        return self._repository.list_exports(source_type, limit, before)

    def download(self, export_id):
        export = self._repository.get_export_for_download(export_id)
        if export is None:
            raise NotFoundError("Export not found.")
        status = export_status(export)
        if status == "MIGRATION_REQUIRED":
            raise ExportConflictError("Legacy PDF requires reviewed migration.")
        if status == "EXPIRED":
            raise ExportExpiredError("PDF retention expired.")
        content = export.pdf_data
        if (not content or len(content) != export.file_size_bytes or len(content) > MAX_PDF
                or not content.startswith(b"%PDF-") or sha256(content).hexdigest() != export.pdf_sha256):
            raise ExportGenerationError("Stored PDF integrity check failed.")
        return export, content

    def delete_export(self, export_id):
        self._repository.delete_export(export_id)

    @staticmethod
    def _slug(value):
        return sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")[:56] or "export"
