from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ChatPdfExport:
    title: str
    question: str
    answer: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    conversation_id: str | None = None
    message_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

