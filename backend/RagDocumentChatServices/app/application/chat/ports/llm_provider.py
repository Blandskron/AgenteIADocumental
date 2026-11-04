from typing import Protocol

from app.domain.chat import ChatMessage
from app.domain.embeddings import SearchResult


class LLMProvider(Protocol):
    def answer_with_context(
        self,
        question: str,
        context: list[SearchResult],
        history: list[ChatMessage] | None = None,
        mode: str = "qa",
    ) -> str:
        ...
