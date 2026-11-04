from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class TransferCreateRequest(BaseModel):
    filename: str = Field(min_length=1)
    direction: Literal["UPLOAD", "DOWNLOAD"]
    status: Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"] = "PENDING"
    progress: int = Field(default=0, ge=0, le=100)
    document_id: str | None = None
    size_bytes: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TransferUpdateRequest(BaseModel):
    status: Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"] | None = None
    progress: int | None = Field(default=None, ge=0, le=100)
    document_id: str | None = None
    size_bytes: int | None = None
    metadata: dict[str, Any] | None = None


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
