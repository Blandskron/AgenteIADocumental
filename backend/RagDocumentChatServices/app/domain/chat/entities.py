from dataclasses import dataclass
from enum import StrEnum


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass(frozen=True)
class ChatMessage:
    role: MessageRole
    content: str


@dataclass(frozen=True)
class AnswerSource:
    document_id: str
    chunk_id: str
    content: str
    score: float
    filename: str | None = None
    chunk_index: int | None = None
    page: int | None = None
    section: str | None = None
    rrf_score: float | None = None


@dataclass(frozen=True)
class ChatAnswer:
    answer: str
    sources: list[AnswerSource]
    provider_status: str = "ok"
