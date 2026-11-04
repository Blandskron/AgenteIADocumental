from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.security import user_id
from app.domain.chat import AnswerSource, ChatMessage, MessageRole
from app.infrastructure.database.models import ChatMessageModel


class ChatHistoryRepositoryPg:
    def __init__(self, session: Session, current_user: dict) -> None:
        self._session = session
        self._owner_user_id = user_id(current_user)

    def get_user_history(self, session_id: str, limit: int = 20) -> list[ChatMessage]:
        # Stored assistant answers can include documents whose access has since changed.
        statement = (
            select(ChatMessageModel)
            .where(
                ChatMessageModel.session_id == session_id,
                ChatMessageModel.owner_user_id == self._owner_user_id,
                ChatMessageModel.role == MessageRole.USER.value,
            )
            .order_by(ChatMessageModel.created_at.desc(), ChatMessageModel.message_id.desc())
            .limit(limit)
        )
        rows = self._session.scalars(statement).all()
        return [
            ChatMessage(role=MessageRole(row.role), content=row.content)
            for row in reversed(rows)
        ]

    def save_user_message(self, session_id: str, content: str) -> None:
        self._insert_message(session_id, MessageRole.USER.value, content, [])

    def save_assistant_message(
        self,
        session_id: str,
        content: str,
        sources: list[AnswerSource],
    ) -> None:
        source_payload = [source.__dict__ for source in sources]
        self._insert_message(session_id, MessageRole.ASSISTANT.value, content, source_payload)

    def _insert_message(self, session_id: str, role: str, content: str, sources: list[dict]) -> None:
        self._session.add(
            ChatMessageModel(
                session_id=session_id,
                owner_user_id=self._owner_user_id,
                role=role,
                content=content,
                sources=sources,
            )
        )
        self._session.commit()
