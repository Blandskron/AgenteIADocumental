from datetime import datetime
from json import dumps
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator


def valid_text(value: str) -> str:
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise ValueError("Text must be valid Unicode.") from exc
    if not value.strip() or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("Text must not be blank or contain control characters.")
    return value


Identifier = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=128), AfterValidator(valid_text)]
Filename = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=512), AfterValidator(valid_text)]
Progress = Annotated[int, Field(strict=True, ge=0, le=100)]
SizeBytes = Annotated[int, Field(strict=True, ge=0, le=9_223_372_036_854_775_807)]


def valid_metadata(value: dict) -> dict:
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


class TransferInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("metadata", check_fields=False)
    @classmethod
    def validate_metadata(cls, value):
        return valid_metadata(value) if value is not None else value


class TransferCreateRequest(TransferInput):
    filename: Filename
    direction: Literal["UPLOAD", "DOWNLOAD"]
    status: Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"] = "PENDING"
    progress: Progress = 0
    document_id: Identifier | None = None
    size_bytes: SizeBytes | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TransferUpdateRequest(TransferInput):
    status: Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"] | None = None
    progress: Progress | None = None
    document_id: Identifier | None = None
    size_bytes: SizeBytes | None = None
    metadata: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set:
            raise ValueError("At least one change is required.")
        if any(getattr(self, field) is None for field in self.model_fields_set - {"document_id", "size_bytes"}):
            raise ValueError("Only document_id and size_bytes can be cleared with null.")
        return self


class TransferResponse(BaseModel):
    transfer_id: str
    owner_user_id: str
    document_id: str | None
    filename: str
    direction: str
    status: str
    progress: int
    size_bytes: int | None
    metadata: dict[str, Any]
    created_at: datetime | None
    updated_at: datetime | None


class CountResponse(BaseModel):
    count: int


class TransferPage(BaseModel):
    items: list[TransferResponse]
    limit: int
    offset: int
    has_more: bool
