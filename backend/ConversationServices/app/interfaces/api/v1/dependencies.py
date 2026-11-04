from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.use_cases.manage_conversations import ManageConversations
from app.config.database import get_session
from app.config.security import require_authenticated_user
from app.infrastructure.database.repositories.conversation_repository_pg import ConversationRepositoryPg


def get_conversation_use_case(
    session: Session = Depends(get_session),
    current_user: dict = Depends(require_authenticated_user),
) -> ManageConversations:
    return ManageConversations(ConversationRepositoryPg(session, current_user))
