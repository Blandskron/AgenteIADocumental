from pydantic import BaseModel


class DocumentProcessResponse(BaseModel):
    document_id: str
    status: str


class DocumentStatusResponse(BaseModel):
    document_id: str
    filename: str
    status: str
    mime_type: str
    storage_path: str


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    status: str
    mime_type: str
    storage_path: str
    metadata: dict
