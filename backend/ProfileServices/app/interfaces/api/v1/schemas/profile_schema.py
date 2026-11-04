from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ProfileResponse(BaseModel):
    profile_id: str | None
    user_id: str
    email: str | None
    phone_number: str | None
    profile_picture_url: str | None
    additional_info: dict[str, Any]
    groups: list[str]
    permissions: list[str]
    created_at: datetime | None
    updated_at: datetime | None

    class Config:
        from_attributes = True


class ProfileUpdateRequest(BaseModel):
    email: str | None = None
    phone_number: str | None = None
    profile_picture_url: str | None = None
    additional_info: dict[str, Any] | None = None


class ProfileUploadResponse(BaseModel):
    url: str

