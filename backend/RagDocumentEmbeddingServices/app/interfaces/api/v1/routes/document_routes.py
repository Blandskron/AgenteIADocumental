from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.application.documents.ports.document_reader import DocumentReader
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


@router.post("/upload", response_model=DocumentUploadResponse)
def upload_document(
    file: UploadFile = File(...),
    metadata: str | None = Form(default=None),
    process: bool = Form(default=True),
    current_user: dict = Depends(require_upload_user),
    use_case: UploadDocument = Depends(get_upload_document),
) -> DocumentUploadResponse:
    document_metadata = {
        **parse_metadata(metadata),
        **build_document_access_metadata(current_user),
    }
    document = use_case.execute(
        filename=file.filename or "document",
        mime_type=detect_mime_type(file),
        file=file.file,
        metadata=document_metadata,
        process=process,
    )
    return DocumentUploadResponse(
        document_id=document.document_id,
        filename=document.filename,
        status=document.status.value,
        mime_type=document.mime_type,
        storage_path=document.storage_path,
        metadata=document.metadata or {},
    )


@router.post("/{document_id}/process", response_model=DocumentProcessResponse)
@router.post("/{document_id}/reindex", response_model=DocumentProcessResponse)
def process_document(
    document_id: str,
    current_user: dict = Depends(require_authenticated_user),
    reader: DocumentReader = Depends(get_document_reader),
    use_case: IngestExistingDocument = Depends(get_ingest_existing_document),
) -> DocumentProcessResponse:
    document = reader.get_by_id(document_id)
    if document is None or not can_manage_document(current_user, document):
        raise DocumentNotFoundError(f"Document {document_id} was not found.")
    use_case.execute(document_id)
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
