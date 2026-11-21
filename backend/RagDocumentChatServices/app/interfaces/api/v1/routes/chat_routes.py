import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.application.chat.use_cases.ask_document_chat import AskDocumentChat
from app.interfaces.api.v1.dependencies import get_ask_document_chat
from app.interfaces.api.v1.schemas.chat_schema import ChatAskRequest, ChatAskResponse, ChatSourceResponse

router = APIRouter()


@router.post("/ask", response_model=ChatAskResponse)
def ask(
    payload: ChatAskRequest,
    stream: bool = Query(default=False),
    use_case: AskDocumentChat = Depends(get_ask_document_chat),
):
    answer = use_case.execute(
        question=payload.question,
        session_id=payload.session_id,
        document_ids=payload.document_ids,
    )
    response_payload = ChatAskResponse(
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
        provider_status=answer.provider_status,
    )
    if stream:
        def _event_stream():
            yield f"event: meta\ndata: {json.dumps({'provider_status': response_payload.provider_status, 'sources': [s.model_dump() for s in response_payload.sources]}, ensure_ascii=False)}\n\n"
            text = response_payload.answer
            chunk_size = 160
            for offset in range(0, len(text), chunk_size):
                yield f"event: delta\ndata: {json.dumps({'delta': text[offset : offset + chunk_size]}, ensure_ascii=False)}\n\n"
            yield f"event: done\ndata: {json.dumps({'answer': text}, ensure_ascii=False)}\n\n"

        return StreamingResponse(_event_stream(), media_type="text/event-stream")
    return response_payload
