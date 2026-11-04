from fastapi import APIRouter, Depends, HTTPException

from app.application.use_cases.manage_conversations import ManageConversations
from app.interfaces.api.v1.dependencies import get_conversation_use_case
from app.interfaces.api.v1.schemas.conversation_schema import (
    ConversationCreateRequest,
    ConversationResponse,
    ConversationUpdateRequest,
    DeleteResponse,
    DocumentIdsResponse,
    MessageCreateRequest,
    MessageResponse,
)

router = APIRouter()


@router.get("/conversations", response_model=list[ConversationResponse])
def list_conversations(include_archived: bool = False, use_case: ManageConversations = Depends(get_conversation_use_case)):
    return [_conversation_response(conversation) for conversation in use_case.list(include_archived)]


@router.post("/conversations", response_model=ConversationResponse)
def create_conversation(payload: ConversationCreateRequest, use_case: ManageConversations = Depends(get_conversation_use_case)):
    return _conversation_response(use_case.create(payload))


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
def get_conversation(conversation_id: str, use_case: ManageConversations = Depends(get_conversation_use_case)):
    conversation = use_case.get(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return _conversation_response(conversation)


@router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
def update_conversation(conversation_id: str, payload: ConversationUpdateRequest, use_case: ManageConversations = Depends(get_conversation_use_case)):
    conversation = use_case.update(conversation_id, payload)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return _conversation_response(conversation)


@router.delete("/conversations/{conversation_id}", response_model=DeleteResponse)
def delete_conversation(conversation_id: str, use_case: ManageConversations = Depends(get_conversation_use_case)):
    return DeleteResponse(deleted=use_case.delete(conversation_id))


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
def list_messages(conversation_id: str, use_case: ManageConversations = Depends(get_conversation_use_case)):
    return [_message_response(message) for message in use_case.list_messages(conversation_id)]


@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse)
def add_message(conversation_id: str, payload: MessageCreateRequest, use_case: ManageConversations = Depends(get_conversation_use_case)):
    message = use_case.add_message(conversation_id, payload)
    if message is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return _message_response(message)


@router.get("/conversations/{conversation_id}/documents", response_model=DocumentIdsResponse)
def list_documents(conversation_id: str, use_case: ManageConversations = Depends(get_conversation_use_case)):
    return DocumentIdsResponse(document_ids=use_case.list_documents(conversation_id))


@router.post("/conversations/{conversation_id}/documents/{document_id}", response_model=DeleteResponse)
def add_document(conversation_id: str, document_id: str, use_case: ManageConversations = Depends(get_conversation_use_case)):
    return DeleteResponse(deleted=use_case.add_document(conversation_id, document_id))


@router.delete("/conversations/{conversation_id}/documents/{document_id}", response_model=DeleteResponse)
def remove_document(conversation_id: str, document_id: str, use_case: ManageConversations = Depends(get_conversation_use_case)):
    return DeleteResponse(deleted=use_case.remove_document(conversation_id, document_id))


def _conversation_response(conversation) -> ConversationResponse:
    return ConversationResponse(
        conversation_id=str(conversation.conversation_id),
        owner_user_id=conversation.owner_user_id,
        title=conversation.title,
        archived=conversation.archived,
        metadata=conversation.metadata_ or {},
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


def _message_response(message) -> MessageResponse:
    return MessageResponse(
        message_id=str(message.message_id),
        conversation_id=str(message.conversation_id),
        owner_user_id=message.owner_user_id,
        role=message.role,
        content=message.content,
        sources=message.sources or [],
        metadata=message.metadata_ or {},
        created_at=message.created_at,
    )
