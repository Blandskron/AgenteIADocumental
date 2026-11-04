from __future__ import annotations

from sqlalchemy.orm import Session

from app.infrastructure.database.models import ConversationDocumentModel, ConversationMessageModel, ConversationModel


class ConversationRepositoryPg:
    def __init__(self, session: Session, current_user: dict) -> None:
        self._session = session
        self._owner_user_id = _owner_user_id(current_user)

    def list(self, include_archived: bool = False) -> list[ConversationModel]:
        statement = self._session.query(ConversationModel).filter(ConversationModel.owner_user_id == self._owner_user_id)
        if not include_archived:
            statement = statement.filter(ConversationModel.archived.is_(False))
        return statement.order_by(ConversationModel.updated_at.desc()).all()

    def create(self, title: str, metadata: dict | None = None) -> ConversationModel:
        conversation = ConversationModel(owner_user_id=self._owner_user_id, title=title.strip() or "Nuevo chat", metadata_=metadata or {})
        self._session.add(conversation)
        self._session.commit()
        self._session.refresh(conversation)
        return conversation

    def get(self, conversation_id: str) -> ConversationModel | None:
        return (
            self._session.query(ConversationModel)
            .filter(ConversationModel.conversation_id == conversation_id, ConversationModel.owner_user_id == self._owner_user_id)
            .first()
        )

    def update(self, conversation_id: str, title: str | None = None, archived: bool | None = None) -> ConversationModel | None:
        conversation = self.get(conversation_id)
        if conversation is None:
            return None
        if title is not None:
            conversation.title = title.strip() or conversation.title
        if archived is not None:
            conversation.archived = archived
        self._session.commit()
        self._session.refresh(conversation)
        return conversation

    def delete(self, conversation_id: str) -> bool:
        conversation = self.get(conversation_id)
        if conversation is None:
            return False
        self._session.delete(conversation)
        self._session.commit()
        return True

    def list_messages(self, conversation_id: str) -> list[ConversationMessageModel]:
        if self.get(conversation_id) is None:
            return []
        return (
            self._session.query(ConversationMessageModel)
            .filter(
                ConversationMessageModel.conversation_id == conversation_id,
                ConversationMessageModel.owner_user_id == self._owner_user_id,
            )
            .order_by(ConversationMessageModel.created_at.asc())
            .all()
        )

    def add_message(self, conversation_id: str, role: str, content: str, sources: list | None = None, metadata: dict | None = None):
        if self.get(conversation_id) is None:
            return None
        message = ConversationMessageModel(
            conversation_id=conversation_id,
            owner_user_id=self._owner_user_id,
            role=role,
            content=content,
            sources=sources or [],
            metadata_=metadata or {},
        )
        self._session.add(message)
        self._session.commit()
        self._session.refresh(message)
        return message

    def list_documents(self, conversation_id: str) -> list[str]:
        return [
            row.document_id
            for row in self._session.query(ConversationDocumentModel)
            .filter(
                ConversationDocumentModel.conversation_id == conversation_id,
                ConversationDocumentModel.owner_user_id == self._owner_user_id,
            )
            .order_by(ConversationDocumentModel.created_at.desc())
            .all()
        ]

    def add_document(self, conversation_id: str, document_id: str) -> bool:
        if self.get(conversation_id) is None:
            return False
        exists = (
            self._session.query(ConversationDocumentModel)
            .filter(
                ConversationDocumentModel.conversation_id == conversation_id,
                ConversationDocumentModel.document_id == document_id,
                ConversationDocumentModel.owner_user_id == self._owner_user_id,
            )
            .first()
        )
        if exists is None:
            self._session.add(
                ConversationDocumentModel(
                    conversation_id=conversation_id,
                    document_id=document_id,
                    owner_user_id=self._owner_user_id,
                )
            )
            self._session.commit()
        return True

    def remove_document(self, conversation_id: str, document_id: str) -> bool:
        row = (
            self._session.query(ConversationDocumentModel)
            .filter(
                ConversationDocumentModel.conversation_id == conversation_id,
                ConversationDocumentModel.document_id == document_id,
                ConversationDocumentModel.owner_user_id == self._owner_user_id,
            )
            .first()
        )
        if row is None:
            return False
        self._session.delete(row)
        self._session.commit()
        return True


def _owner_user_id(current_user: dict) -> str:
    return str(current_user.get("user_id") or current_user.get("sub") or current_user.get("username") or "unknown")
