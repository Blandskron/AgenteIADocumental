from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class GoogleDriveConnection:
    connection_id: str
    owner_user_id: str
    provider_account_email: str | None
    scopes: list[str]
    access_token_encrypted: str
    refresh_token_encrypted: str | None
    expires_at: datetime | None
    metadata_: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class GoogleDriveImport:
    import_id: str
    owner_user_id: str
    status: str
    total_files: int
    processed_files: int
    failed_files: int
    metadata_: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class GoogleDriveImportFile:
    import_file_id: str
    import_id: str
    google_file_id: str
    filename: str
    mime_type: str
    export_mime_type: str | None
    size_bytes: int | None
    status: str
    document_id: str | None
    metadata_: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
