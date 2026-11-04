from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Conversation:
    conversation_id: str
    owner_user_id: str
    title: str
    archived: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class ConversationMessage:
    message_id: str
    conversation_id: str
    owner_user_id: str
    role: str
    content: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
