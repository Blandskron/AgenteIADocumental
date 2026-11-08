from uuid import UUID
from typing import Annotated
import re
from fastapi import APIRouter, Depends, Header, Path, Query
from fastapi.responses import Response

from app.application.use_cases.manage_exports import ManageExports, export_status
from app.interfaces.api.v1.dependencies import get_export_use_case
from app.interfaces.api.v1.schemas.export_schema import ChatPdfExportRequest, ExportResponse

router = APIRouter()
ExportId = Annotated[str, Path(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")]


def download_filename(export):
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}\.pdf", export.filename or ""):
        return export.filename
    return ManageExports._slug(export.title) + ".pdf"


@router.post("/exports/chat-message/pdf", response_model=ExportResponse)
def create_chat_message_pdf(
    payload: ChatPdfExportRequest,
    idempotency_key: UUID | None = Header(default=None),
    use_case: ManageExports = Depends(get_export_use_case),
):
    export = use_case.create_chat_pdf_export(payload, str(idempotency_key) if idempotency_key else None)
    return _export_response(export)


@router.get("/exports", response_model=list[ExportResponse])
def list_exports(
    source_type: str | None = Query(default=None, min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_-]+$"),
    use_case: ManageExports = Depends(get_export_use_case),
):
    return [_export_response(export) for export in use_case.list_exports(source_type)]


@router.get("/exports/{export_id}", response_model=ExportResponse)
def get_export(export_id: ExportId, use_case: ManageExports = Depends(get_export_use_case)):
    return _export_response(use_case.get_export(export_id))


@router.get("/exports/{export_id}/status", response_model=ExportResponse)
def get_export_status(export_id: ExportId, use_case: ManageExports = Depends(get_export_use_case)):
    return _export_response(use_case.get_export(export_id))


@router.get("/exports/{export_id}/download")
def download_export(export_id: ExportId, use_case: ManageExports = Depends(get_export_use_case)):
    export, content = use_case.download(export_id)
    filename = download_filename(export)
    return Response(content=content, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff", "ETag": '"' + export.pdf_sha256 + '"',
    })


@router.delete("/exports/{export_id}")
def delete_export(export_id: ExportId, use_case: ManageExports = Depends(get_export_use_case)):
    use_case.delete_export(export_id)
    return {"deleted": True}

def _export_response(export) -> ExportResponse:
    return ExportResponse(
        export_id=str(export.export_id),
        source_type=export.source_type,
        source_id=export.source_id,
        conversation_id=export.conversation_id,
        message_id=export.message_id,
        title=export.title,
        format=export.format,
        status=export_status(export),
        filename=download_filename(export),
        mime_type="application/pdf",
        file_size_bytes=export.file_size_bytes,
        metadata=export.metadata_ or {},
        download_url=f"/api/v1/exports/{export.export_id}/download",
        created_at=export.created_at,
        updated_at=export.updated_at,
        expires_at=export.expires_at, sha256=export.pdf_sha256,
    )

