from typing import Protocol

from app.domain.chat import AnswerSource, ChatMessage


class ChatHistoryRepository(Protocol):
    def get_user_history(self, session_id: str, limit: int = 20) -> list[ChatMessage]:
        ...

    def save_turn(
        self,
        session_id: str,
        question: str,
        answer: str,
        sources: list[AnswerSource],
    ) -> None:
        ...
