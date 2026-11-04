from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AuthUrlResponse(BaseModel):
    authorization_url: str
    state: str


class GoogleDriveConnectRequest(BaseModel):
    code: str = Field(min_length=1)


class GoogleDriveConnectionResponse(BaseModel):
    connected: bool
    provider_account_email: str | None = None
    scopes: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None


class GoogleDriveFileRequest(BaseModel):
    file_id: str = Field(min_length=1)
    name: str | None = None
    mime_type: str | None = None
    export_mime_type: str | None = None


class GoogleDriveImportRequest(BaseModel):
    files: list[GoogleDriveFileRequest] = Field(min_length=1)
    folder_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class GoogleDriveImportFileResponse(BaseModel):
    import_file_id: str
    import_id: str
    google_file_id: str
    filename: str
    mime_type: str
    export_mime_type: str | None
    size_bytes: int | None
    status: str
    document_id: str | None
    metadata: dict[str, Any]
    error_message: str | None
    created_at: datetime | None
    updated_at: datetime | None


class GoogleDriveImportResponse(BaseModel):
    import_id: str
    owner_user_id: str
    status: str
    total_files: int
    processed_files: int
    failed_files: int
    metadata: dict[str, Any]
    error_message: str | None
    created_at: datetime | None
    updated_at: datetime | None


class GoogleDriveImportWithFilesResponse(GoogleDriveImportResponse):
    files: list[GoogleDriveImportFileResponse]
