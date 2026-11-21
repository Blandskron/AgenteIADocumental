from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config.security import user_id
from app.domain.chat import AnswerSource, ChatMessage, MessageRole
from app.infrastructure.database.models import ChatMessageModel, ConversationMessageModel
from app.shared.constants import MAX_HISTORY_MESSAGE_LENGTH


class ChatHistoryRepositoryPg:
    def __init__(self, session: Session, current_user: dict) -> None:
        self._session = session
        self._owner_user_id = user_id(current_user)

    def get_user_history(self, session_id: str, limit: int = 20) -> list[ChatMessage]:
        # Primary source of truth: ConversationServices' conversation_messages scoped to owner.
        # Stored assistant answers are excluded because document access may have been revoked.
        conversation_stmt = (
            select(func.left(ConversationMessageModel.content, MAX_HISTORY_MESSAGE_LENGTH))
            .where(
                ConversationMessageModel.conversation_id == session_id,
                ConversationMessageModel.owner_user_id == self._owner_user_id,
                ConversationMessageModel.role == MessageRole.USER.value,
            )
            .order_by(
                ConversationMessageModel.created_at.desc(),
                ConversationMessageModel.message_id.desc(),
            )
            .limit(limit)
        )
        rows = self._session.scalars(conversation_stmt).all()
        if not rows:
            # Backward compatibility for sessions persisted only in legacy chat_messages.
            legacy_stmt = (
                select(func.left(ChatMessageModel.content, MAX_HISTORY_MESSAGE_LENGTH))
                .where(
                    ChatMessageModel.session_id == session_id,
                    ChatMessageModel.owner_user_id == self._owner_user_id,
                    ChatMessageModel.role == MessageRole.USER.value,
                )
                .order_by(ChatMessageModel.created_at.desc(), ChatMessageModel.message_id.desc())
                .limit(limit)
            )
            rows = self._session.scalars(legacy_stmt).all()
        return [
            ChatMessage(role=MessageRole.USER, content=content)
            for content in reversed(rows)
        ]

    def save_turn(
        self,
        session_id: str,
        question: str,
        answer: str,
        sources: list[AnswerSource],
    ) -> None:
        self._session.add_all([
            ChatMessageModel(
                session_id=session_id,
                owner_user_id=self._owner_user_id,
                role=MessageRole.USER.value,
                content=question,
                sources=[],
            ),
            ChatMessageModel(
                session_id=session_id,
                owner_user_id=self._owner_user_id,
                role=MessageRole.ASSISTANT.value,
                content=answer,
                sources=[source.__dict__ for source in sources],
            ),
        ])
        self._session.commit()
