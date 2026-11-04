from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class TransferEvent:
    transfer_id: str
    owner_user_id: str
    filename: str
    direction: str
    status: str
    progress: int = 0
    document_id: str | None = None
    size_bytes: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None
