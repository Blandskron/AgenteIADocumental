from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ConversationCreateRequest(BaseModel):
    title: str = "Nuevo chat"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationUpdateRequest(BaseModel):
    title: str | None = None
    archived: bool | None = None


class ConversationResponse(BaseModel):
    conversation_id: str
    owner_user_id: str
    title: str
    archived: bool
    metadata: dict[str, Any]
    created_at: datetime | None
    updated_at: datetime | None


class MessageCreateRequest(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(min_length=1)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MessageResponse(BaseModel):
    message_id: str
    conversation_id: str
    owner_user_id: str
    role: str
    content: str
    sources: list[dict[str, Any]]
    metadata: dict[str, Any]
    created_at: datetime | None


class DocumentIdsResponse(BaseModel):
    document_ids: list[str]


class DeleteResponse(BaseModel):
    deleted: bool
