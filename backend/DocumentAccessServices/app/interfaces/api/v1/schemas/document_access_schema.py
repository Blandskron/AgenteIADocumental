from datetime import datetime
from json import dumps
from typing import Annotated, Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


Identifier = Annotated[str, StringConstraints(min_length=1, max_length=128, pattern=r"^[^\x00-\x1f\x7f]+$")]
NotificationStatus = Literal["UNREAD", "READ", "ARCHIVED"]
T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    limit: int
    offset: int
    has_more: bool


class DocumentContentResponse(BaseModel):
    document_id: str
    filename: str
    content: str
    chunk_count: int


class DocumentDeleteResponse(BaseModel):
    document_id: str
    filename: str
    deleted: bool
    file_deleted: bool


class DocumentAssignmentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assigned_to_user_id: str = Field(min_length=1, max_length=19, pattern=r"^[1-9][0-9]*$")
    allow_download: bool = True
    due_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value):
        pending = [(value, 0)]
        while pending:
            item, depth = pending.pop()
            if depth > 16:
                raise ValueError("Metadata exceeds 16 levels.")
            if isinstance(item, dict):
                pending.extend((key, depth + 1) for key in item)
                pending.extend((child, depth + 1) for child in item.values())
            elif isinstance(item, list):
                pending.extend((child, depth + 1) for child in item)
            elif isinstance(item, str) and "\x00" in item:
                raise ValueError("Metadata cannot contain null bytes.")
        try:
            encoded = dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
        except (ValueError, TypeError, RecursionError, UnicodeError) as exc:
            raise ValueError("Metadata must be valid JSON.") from exc
        if len(encoded) > 16_384:
            raise ValueError("Metadata exceeds 16384 UTF-8 bytes.")
        return value


class DocumentAssignmentActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=2000, pattern=r"^[^\x00]*$")
    signature_value: str | None = Field(default=None, max_length=4096, pattern=r"^[^\x00]*$")


class DocumentAssignmentResponse(BaseModel):
    assignment_id: str
    document_id: str
    tenant_id: str
    assigned_to_user_id: str
    assigned_by_user_id: str
    assigned_by_role: str | None = None
    status: str
    rejection_reason: str | None = None
    signature_value: str | None = None
    signed_at: datetime | None = None
    due_at: datetime | None = None
    allow_download: bool = True
    metadata: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class DocumentAssignmentEventResponse(BaseModel):
    event_id: str
    assignment_id: str
    actor_user_id: str
    action: str
    reason: str | None = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime


class NotificationResponse(BaseModel):
    notification_id: str
    tenant_id: str | None = None
    recipient_user_id: str
    actor_user_id: str | None = None
    document_id: str | None = None
    assignment_id: str | None = None
    type: str
    title: str
    body: str
    status: str
    metadata: dict = Field(default_factory=dict)
    read_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
