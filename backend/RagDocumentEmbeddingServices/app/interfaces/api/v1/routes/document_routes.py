import os

from fastapi import APIRouter, Depends, File, Form, Header, Response, UploadFile, status

from app.application.documents.ports.document_reader import DocumentReader
from app.application.documents.use_cases.import_markdown_batch import ImportMarkdownBatch
from app.application.documents.use_cases.ingest_existing_document import IngestExistingDocument
from app.application.documents.use_cases.upload_document import UploadDocument
from app.config.security import (
    build_document_access_metadata,
    can_access_document,
    can_manage_document,
    require_authenticated_user,
    require_upload_user,
)
from app.domain.documents.exceptions import DocumentNotFoundError
from app.interfaces.api.v1.dependencies import get_document_reader, get_ingest_existing_document, get_upload_document
from app.interfaces.api.v1.form_utils import detect_mime_type, parse_metadata
from app.interfaces.api.v1.schemas.document_schema import (
    DocumentProcessResponse,
    DocumentStatusResponse,
    DocumentUploadResponse,
)

router = APIRouter()


def _is_async_ingest_enabled() -> bool:
    return os.environ.get("ASYNC_INGEST_ENABLED", "false").strip().lower() in {"1", "true", "yes"}


@router.post(
    "/upload", response_model=DocumentUploadResponse,
    responses={409: {"description": "La empresa o el área cambió. Recargar sesión antes de reintentar."}},
)
def upload_document(
    response: Response,
    file: UploadFile = File(...),
    metadata: str | None = Form(default=None),
    process: bool = Form(default=True),
    current_user: dict = Depends(require_upload_user),
    use_case: UploadDocument = Depends(get_upload_document),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> DocumentUploadResponse:
    document_metadata = {
        **parse_metadata(metadata),
        **build_document_access_metadata(current_user),
    }
    clean_key = idempotency_key if isinstance(idempotency_key, str) else None
    async_mode = _is_async_ingest_enabled()
    effective_process = False if async_mode else process
    document = use_case.execute(
        filename=file.filename or "document",
        mime_type=detect_mime_type(file),
        file=file.file,
        metadata=document_metadata,
        process=effective_process,
        idempotency_key=clean_key,
    )
    if async_mode and document.status.value == "PENDING":
        response.status_code = status.HTTP_202_ACCEPTED
    return DocumentUploadResponse(
        document_id=document.document_id,
        filename=document.filename,
        status=document.status.value,
        mime_type=document.mime_type,
        storage_path=document.storage_path,
        metadata=document.metadata or {},
    )


@router.post("/import-batch")
def import_markdown_batch(
    files: list[UploadFile] = File(...),
    process: bool = Form(default=True),
    current_user: dict = Depends(require_upload_user),
    use_case: UploadDocument = Depends(get_upload_document),
) -> dict:
    batch_use_case = ImportMarkdownBatch(use_case)
    base_metadata = build_document_access_metadata(current_user)
    if len(files) == 1 and (files[0].filename or "").lower().endswith(".zip"):
        raw = files[0].file.read(25 * 1024 * 1024)
        return batch_use_case.execute_zip(raw, base_metadata=base_metadata, process=process).to_dict()
    entries = [(item.filename or "note.md", item.file.read(5 * 1024 * 1024)) for item in files]
    return batch_use_case.execute_files(entries, base_metadata=base_metadata, process=process).to_dict()


@router.post(
    "/{document_id}/process", response_model=DocumentProcessResponse,
    responses={409: {"description": "Document is being modified."}},
)
@router.post(
    "/{document_id}/reindex", response_model=DocumentProcessResponse,
    responses={409: {"description": "Document is being modified."}},
)
def process_document(
    document_id: str,
    current_user: dict = Depends(require_authenticated_user),
    reader: DocumentReader = Depends(get_document_reader),
    use_case: IngestExistingDocument = Depends(get_ingest_existing_document),
) -> DocumentProcessResponse:
    document = reader.get_by_id(document_id)
    if document is None or not can_manage_document(current_user, document):
        raise DocumentNotFoundError(f"Document {document_id} was not found.")
    use_case.execute(document_id, authorize=lambda locked_document: can_manage_document(current_user, locked_document))
    return DocumentProcessResponse(document_id=document_id, status="PROCESSED")


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
def document_status(
    document_id: str,
    current_user: dict = Depends(require_authenticated_user),
    reader: DocumentReader = Depends(get_document_reader),
) -> DocumentStatusResponse:
    document = reader.get_by_id(document_id)
    if document is None:
        raise DocumentNotFoundError(f"Document {document_id} was not found.")
    if not can_access_document(current_user, document):
        raise DocumentNotFoundError(f"Document {document_id} was not found.")
    return DocumentStatusResponse(
        document_id=document.document_id,
        filename=document.filename,
        status=document.status.value,
        mime_type=document.mime_type,
        storage_path=document.storage_path,
    )
