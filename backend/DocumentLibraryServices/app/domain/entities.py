from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Folder:
    folder_id: str
    name: str
    owner_user_id: str
    parent_folder_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class LibraryDocument:
    document_id: str
    filename: str
    mime_type: str
    status: str
    updated_at: datetime | None = None
    folder_id: str | None = None
    favorite: bool = False
