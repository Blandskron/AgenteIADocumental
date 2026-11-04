from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from app.application.use_cases.manage_exports import ManageExports
from app.interfaces.api.v1.dependencies import get_export_use_case
from app.interfaces.api.v1.schemas.export_schema import ChatPdfExportRequest, ExportResponse

router = APIRouter()


@router.post("/exports/chat-message/pdf", response_model=ExportResponse)
def create_chat_message_pdf(
    payload: ChatPdfExportRequest,
    use_case: ManageExports = Depends(get_export_use_case),
):
    export = use_case.create_chat_pdf_export(payload)
    return _export_response(export)


@router.get("/exports", response_model=list[ExportResponse])
def list_exports(
    source_type: str | None = Query(default=None),
    use_case: ManageExports = Depends(get_export_use_case),
):
    return [_export_response(export) for export in use_case.list_exports(source_type)]


@router.get("/exports/{export_id}", response_model=ExportResponse)
def get_export(export_id: str, use_case: ManageExports = Depends(get_export_use_case)):
    return _export_response(use_case.get_export(export_id))


@router.get("/exports/{export_id}/status", response_model=ExportResponse)
def get_export_status(export_id: str, use_case: ManageExports = Depends(get_export_use_case)):
    return _export_response(use_case.get_export(export_id))


@router.get("/exports/{export_id}/download")
def download_export(export_id: str, use_case: ManageExports = Depends(get_export_use_case)):
    export = use_case.get_export(export_id)
    path = use_case.download_path(export_id)
    return FileResponse(
        path=str(path),
        media_type=export.mime_type,
        filename=export.filename,
        headers={"Content-Disposition": f'attachment; filename="{export.filename}"'},
    )


def _export_response(export) -> ExportResponse:
    return ExportResponse(
        export_id=str(export.export_id),
        source_type=export.source_type,
        source_id=export.source_id,
        conversation_id=export.conversation_id,
        message_id=export.message_id,
        title=export.title,
        format=export.format,
        status=export.status,
        filename=export.filename,
        mime_type=export.mime_type,
        file_size_bytes=export.file_size_bytes,
        metadata=export.metadata_ or {},
        download_url=f"/api/v1/exports/{export.export_id}/download",
        created_at=export.created_at,
        updated_at=export.updated_at,
    )

