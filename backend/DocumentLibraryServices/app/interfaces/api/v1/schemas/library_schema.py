from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FolderCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    parent_folder_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class FolderUpdateRequest(BaseModel):
    name: str | None = None
    metadata: dict[str, Any] | None = None


class FolderResponse(BaseModel):
    folder_id: str
    name: str
    parent_folder_id: str | None
    owner_user_id: str
    metadata: dict[str, Any]
    document_count: int = 0
    created_at: datetime | None
    updated_at: datetime | None


class DocumentResponse(BaseModel):
    document_id: str
    filename: str
    mime_type: str
    status: str
    chunk_count: int = 0
    updated_at: datetime | None


class DocumentMoveRequest(BaseModel):
    folder_id: str | None = None


class DeleteResponse(BaseModel):
    deleted: bool


class CountResponse(BaseModel):
    count: int


class ActionResponse(BaseModel):
    success: bool
