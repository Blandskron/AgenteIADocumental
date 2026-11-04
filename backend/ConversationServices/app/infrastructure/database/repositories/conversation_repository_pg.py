from __future__ import annotations

from sqlalchemy import delete, select, true
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.infrastructure.database.models import ConversationDocumentModel, ConversationMessageModel, ConversationModel, documents
from app.infrastructure.database.repositories.document_access import document_access_filter


class ConversationRepositoryPg:
    def __init__(self, session: Session, current_user: dict) -> None:
        self._session = session
        self._current_user = current_user
        self._owner_user_id = str(current_user["user_id"])

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
        statement = (
            select(ConversationDocumentModel.document_id)
            .join(documents, documents.c.document_id == ConversationDocumentModel.document_id)
            .where(
                ConversationDocumentModel.conversation_id == conversation_id,
                ConversationDocumentModel.owner_user_id == self._owner_user_id,
                self._owns_conversation(conversation_id),
                document_access_filter(self._current_user, self._owner_user_id),
            )
            .order_by(ConversationDocumentModel.created_at.desc())
        )
        return list(self._session.scalars(statement))

    def add_document(self, conversation_id: str, document_id: str) -> bool:
        # Keep both FK targets from being deleted between the access check and insert.
        allowed_document = (
            select(documents.c.document_id)
            .join(ConversationModel, true())
            .where(
                ConversationModel.conversation_id == conversation_id,
                ConversationModel.owner_user_id == self._owner_user_id,
                documents.c.document_id == document_id,
                document_access_filter(self._current_user, self._owner_user_id),
            )
            .with_for_update(of=(ConversationModel, documents), read=True, key_share=True)
        )
        if self._session.scalar(allowed_document) is None:
            return False

        self._session.execute(
            insert(ConversationDocumentModel)
            .values(
                conversation_id=conversation_id,
                document_id=document_id,
                owner_user_id=self._owner_user_id,
            )
            .on_conflict_do_nothing(index_elements=["conversation_id", "document_id"])
        )
        self._session.commit()
        return True

    def remove_document(self, conversation_id: str, document_id: str) -> bool:
        removed = self._session.scalar(
            delete(ConversationDocumentModel)
            .where(
                ConversationDocumentModel.conversation_id == conversation_id,
                ConversationDocumentModel.document_id == document_id,
                ConversationDocumentModel.owner_user_id == self._owner_user_id,
                self._owns_conversation(conversation_id),
            )
            .returning(ConversationDocumentModel.document_id)
        )
        self._session.commit()
        return removed is not None

    def _owns_conversation(self, conversation_id: str):
        return select(1).where(
            ConversationModel.conversation_id == conversation_id,
            ConversationModel.owner_user_id == self._owner_user_id,
        ).exists()
