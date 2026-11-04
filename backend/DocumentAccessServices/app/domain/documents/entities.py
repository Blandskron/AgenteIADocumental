from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DocumentFile:
    document_id: str
    filename: str
    mime_type: str
    status: str
    storage_path: str
    metadata: dict
    created_at: datetime
    updated_at: datetime
    allow_download: bool = True
    processed_at: datetime | None = None
    processing_error: str | None = None


@dataclass(frozen=True)
class DocumentContent:
    document_id: str
    filename: str
    content: str
    chunk_count: int


@dataclass(frozen=True)
class DocumentDeleteResult:
    document_id: str
    filename: str
    deleted: bool
    file_deleted: bool
