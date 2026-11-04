from datetime import datetime
from json import dumps
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


MAX_TITLE_LENGTH = 256
MAX_METADATA_BYTES = 16_384
MAX_SOURCES_BYTES = 262_144


def _validate_json_size(value, max_bytes: int):
    try:
        encoded = dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (ValueError, RecursionError) as exc:
        raise ValueError("Value must be valid JSON.") from exc
    if len(encoded) > max_bytes:
        raise ValueError(f"JSON value exceeds {max_bytes} UTF-8 bytes.")
    return value


class RequestWithMetadata(BaseModel):
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value):
        return _validate_json_size(value, MAX_METADATA_BYTES)


class ConversationCreateRequest(RequestWithMetadata):
    title: str = Field(default="Nuevo chat", max_length=MAX_TITLE_LENGTH)


class ConversationUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=MAX_TITLE_LENGTH)
    archived: bool | None = None


class ConversationResponse(BaseModel):
    conversation_id: str
    owner_user_id: str
    title: str
    archived: bool
    metadata: dict[str, Any]
    created_at: datetime | None
    updated_at: datetime | None


class MessageCreateRequest(RequestWithMetadata):
    role: Literal["user", "assistant", "system"]
    content: str = Field(min_length=1, max_length=32_768)
    sources: list[dict[str, Any]] = Field(default_factory=list, max_length=50)

    @field_validator("sources")
    @classmethod
    def validate_sources(cls, value):
        return _validate_json_size(value, MAX_SOURCES_BYTES)


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
