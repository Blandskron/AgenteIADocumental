from datetime import datetime
from json import dumps
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints, field_validator, model_validator


def valid_text(value: str) -> str:
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise ValueError("Text must be valid Unicode.") from exc
    if not value.strip() or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("Text must not be blank or contain control characters.")
    return value


Identifier = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=128), AfterValidator(valid_text)]


def clean_name(value):
    if not isinstance(value, str):
        raise ValueError("Folder name must be text.")
    return valid_text(value).strip()


FolderName = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=200), BeforeValidator(clean_name)]


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


class FolderInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("metadata", check_fields=False)
    @classmethod
    def validate_metadata(cls, value):
        return valid_metadata(value) if value is not None else value


class FolderCreateRequest(FolderInput):
    name: FolderName
    parent_folder_id: Identifier | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class FolderUpdateRequest(FolderInput):
    name: FolderName | None = None
    metadata: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set:
            raise ValueError("At least one change is required.")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Changes must not be null.")
        return self


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
    model_config = ConfigDict(extra="forbid")
    folder_id: Identifier | None = Field(...)


class DeleteResponse(BaseModel):
    deleted: bool


class CountResponse(BaseModel):
    count: int


class ActionResponse(BaseModel):
    success: bool
