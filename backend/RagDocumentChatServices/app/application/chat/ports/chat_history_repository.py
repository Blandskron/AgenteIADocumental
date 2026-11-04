from typing import Protocol

from app.domain.chat import AnswerSource, ChatMessage


class ChatHistoryRepository(Protocol):
    def get_user_history(self, session_id: str, limit: int = 20) -> list[ChatMessage]:
        ...

    def save_user_message(self, session_id: str, content: str) -> None:
        ...

    def save_assistant_message(
        self,
        session_id: str,
        content: str,
        sources: list[AnswerSource],
    ) -> None:
        ...
