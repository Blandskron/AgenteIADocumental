from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DocumentSummary:
    document_id: str
    filename: str
    mime_type: str
    status: str
    chunk_count: int
    created_at: datetime
    updated_at: datetime
    processed_at: datetime | None = None
    snippet: str | None = None


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    document_id: str
    chunk_index: int
    content: str
    created_at: datetime


@dataclass(frozen=True)
class DocumentSearchResult:
    items: list[DocumentSummary]
    total: int
    limit: int
    offset: int


@dataclass(frozen=True)
class ChatDocumentSelection:
    session_id: str | None
    documents: list[DocumentSummary]
    suggested_prompt: str
