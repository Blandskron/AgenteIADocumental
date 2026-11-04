from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ChatPdfExportRequest(BaseModel):
    conversation_id: str | None = None
    message_id: str | None = None
    title: str = "Respuesta documental"
    question: str = ""
    answer: str = Field(min_length=1)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExportResponse(BaseModel):
    export_id: str
    source_type: str
    source_id: str | None
    conversation_id: str | None
    message_id: str | None
    title: str
    format: str
    status: str
    filename: str
    mime_type: str
    file_size_bytes: int
    metadata: dict[str, Any]
    download_url: str
    created_at: datetime | None
    updated_at: datetime | None

