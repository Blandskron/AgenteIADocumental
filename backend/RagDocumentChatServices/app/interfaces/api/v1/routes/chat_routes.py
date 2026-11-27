import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.application.chat.use_cases.ask_document_chat import AskDocumentChat
from app.interfaces.api.v1.dependencies import get_ask_document_chat
from app.interfaces.api.v1.schemas.chat_schema import ChatAskRequest, ChatAskResponse, ChatSourceResponse

router = APIRouter()


def _to_source_response(source) -> ChatSourceResponse:
    return ChatSourceResponse(
        document_id=source.document_id,
        chunk_id=source.chunk_id,
        content=source.content,
        score=source.score,
        filename=source.filename,
        chunk_index=source.chunk_index,
        page=source.page,
        section=source.section,
        rrf_score=source.rrf_score,
    )


@router.post("/ask", response_model=ChatAskResponse)
def ask(
    payload: ChatAskRequest,
    stream: bool = Query(default=False),
    use_case: AskDocumentChat = Depends(get_ask_document_chat),
):
    if stream:
        def _event_stream():
            for event_name, data in use_case.execute_stream(
                question=payload.question,
                session_id=payload.session_id,
                document_ids=payload.document_ids,
            ):
                if event_name == "meta" and isinstance(data, dict):
                    meta_payload = {
                        "provider_status": data.get("provider_status", "ok"),
                        "sources": [_to_source_response(s).model_dump() for s in data.get("sources", [])],
                    }
                    yield f"event: meta\ndata: {json.dumps(meta_payload, ensure_ascii=False)}\n\n"
                elif event_name == "delta":
                    yield f"event: delta\ndata: {json.dumps({'delta': str(data)}, ensure_ascii=False)}\n\n"
                elif event_name == "done":
                    yield f"event: done\ndata: {json.dumps({'answer': str(data)}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            _event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    answer = use_case.execute(
        question=payload.question,
        session_id=payload.session_id,
        document_ids=payload.document_ids,
    )
    return ChatAskResponse(
        answer=answer.answer,
        sources=[_to_source_response(source) for source in answer.sources],
        provider_status=answer.provider_status,
    )
