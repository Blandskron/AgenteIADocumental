from fastapi import APIRouter, Depends

from app.application.chat.use_cases.ask_document_chat import AskDocumentChat
from app.interfaces.api.v1.dependencies import get_ask_document_chat
from app.interfaces.api.v1.schemas.chat_schema import ChatAskRequest, ChatAskResponse, ChatSourceResponse

router = APIRouter()


@router.post("/ask", response_model=ChatAskResponse)
def ask(
    payload: ChatAskRequest,
    use_case: AskDocumentChat = Depends(get_ask_document_chat),
) -> ChatAskResponse:
    answer = use_case.execute(
        question=payload.question,
        session_id=payload.session_id,
        document_ids=payload.document_ids,
    )
    return ChatAskResponse(
        answer=answer.answer,
        sources=[
            ChatSourceResponse(
                document_id=source.document_id,
                chunk_id=source.chunk_id,
                content=source.content,
                score=source.score,
                filename=source.filename,
            )
            for source in answer.sources
        ],
    )
