from dataclasses import dataclass
from enum import StrEnum


class DocumentStatus(StrEnum):
    PENDING = "PENDING"
    REINDEX_REQUIRED = "REINDEX_REQUIRED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class Document:
    document_id: str
    filename: str
    storage_path: str
    mime_type: str
    status: DocumentStatus
    metadata: dict | None = None
