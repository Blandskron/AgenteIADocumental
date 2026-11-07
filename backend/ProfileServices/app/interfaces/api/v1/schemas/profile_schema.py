from datetime import datetime
from typing import Any
import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, TypeAdapter, field_validator, model_validator

from app.domain.profile_limits import validate_metadata


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
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
    version: int


class ProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    expected_version: int = Field(ge=0, le=2**63 - 2)
    email: EmailStr | None = Field(default=None, max_length=254)
    phone_number: str | None = Field(default=None, max_length=32)
    profile_picture_url: str | None = Field(default=None, max_length=2048)
    additional_info: dict[str, Any] | None = None

    @field_validator("email", "phone_number", "profile_picture_url", mode="before")
    @classmethod
    def normalize_contact(cls, value):
        if value is None:
            return None
        if type(value) is not str or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError("Contact fields must be text without control characters.")
        return value.strip() or None

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, value):
        if value is not None and (not re.fullmatch(r"\+?[0-9 ()\-.x#]{3,32}", value)
                                  or sum(c.isdigit() for c in value) < 3):
            raise ValueError("Invalid phone format.")
        return value

    @field_validator("profile_picture_url")
    @classmethod
    def validate_avatar_url(cls, value):
        if value is not None:
            url = TypeAdapter(HttpUrl).validate_python(value)
            normalized = str(url)
            if (url.username is not None or url.password is not None or url.fragment is not None
                    or url.port == 0 or len(normalized) > 2048):
                raise ValueError("Avatar URL exceeds allowed limits.")
            return normalized
        return value

    @field_validator("additional_info")
    @classmethod
    def bounded_metadata(cls, value):
        return validate_metadata(value)

    @model_validator(mode="after")
    def require_changes(self):
        if not self.model_fields_set - {"expected_version"}:
            raise ValueError("At least one profile field is required.")
        return self


class ProfileUploadResponse(BaseModel):
    url: str

