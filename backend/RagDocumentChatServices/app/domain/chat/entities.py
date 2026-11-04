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


@dataclass(frozen=True)
class ChatAnswer:
    answer: str
    sources: list[AnswerSource]
