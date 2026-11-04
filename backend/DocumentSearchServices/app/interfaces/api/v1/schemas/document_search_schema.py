from datetime import datetime

from pydantic import BaseModel, Field


class DocumentSummaryResponse(BaseModel):
    document_id: str
    filename: str
    mime_type: str
    status: str
    metadata: dict
    chunk_count: int
    created_at: datetime
    updated_at: datetime
    processed_at: datetime | None = None
    processing_error: str | None = None
    snippet: str | None = None


class DocumentSearchResponse(BaseModel):
    items: list[DocumentSummaryResponse]
    total: int
    limit: int
    offset: int


class DocumentChunkResponse(BaseModel):
    chunk_id: str
    document_id: str
    chunk_index: int
    content: str
    metadata: dict
    created_at: datetime


class DocumentChunksResponse(BaseModel):
    items: list[DocumentChunkResponse]
    total: int
    limit: int
    offset: int


class ChatSelectionRequest(BaseModel):
    document_ids: list[str] = Field(min_length=1)
    session_id: str | None = None


class ChatSelectionResponse(BaseModel):
    session_id: str | None = None
    documents: list[DocumentSummaryResponse]
    suggested_prompt: str
