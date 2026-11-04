from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints


NO_NULL_BYTES = r"^[^\x00]*$"
Identifier = Annotated[str, StringConstraints(min_length=1, max_length=128, pattern=NO_NULL_BYTES)]


class DocumentSummaryResponse(BaseModel):
    document_id: str
    filename: str
    mime_type: str
    status: str
    chunk_count: int
    created_at: datetime
    updated_at: datetime
    processed_at: datetime | None = None
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
    created_at: datetime


class DocumentChunksResponse(BaseModel):
    items: list[DocumentChunkResponse]
    total: int
    limit: int
    offset: int


class ChatSelectionRequest(BaseModel):
    document_ids: list[Identifier] = Field(min_length=1, max_length=12)
    session_id: Identifier | None = None


class ChatSelectionResponse(BaseModel):
    session_id: str | None = None
    documents: list[DocumentSummaryResponse]
    suggested_prompt: str
