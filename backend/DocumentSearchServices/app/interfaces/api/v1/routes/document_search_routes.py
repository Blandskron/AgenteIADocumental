from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from app.application.documents.use_cases.build_chat_context import BuildChatContext
from app.application.documents.use_cases.get_document_chunks import GetDocumentChunks
from app.application.documents.use_cases.get_document_detail import GetDocumentDetail
from app.application.documents.use_cases.search_documents import SearchDocuments
from app.domain.documents import ChatDocumentSelection, DocumentChunk, DocumentSearchResult, DocumentSummary
from app.interfaces.api.v1.dependencies import (
    get_build_chat_context,
    get_document_chunks,
    get_document_detail,
    get_search_documents,
)
from app.interfaces.api.v1.schemas.document_search_schema import (
    NO_NULL_BYTES,
    ChatSelectionRequest,
    ChatSelectionResponse,
    DocumentChunkResponse,
    DocumentChunksResponse,
    DocumentSearchResponse,
    DocumentSummaryResponse,
)

router = APIRouter()

SearchTerm = Annotated[str | None, Query(max_length=256, pattern=NO_NULL_BYTES)]
PageLimit = Annotated[int, Query(ge=1, le=100)]
PageOffset = Annotated[int, Query(ge=0, le=10_000)]
DocumentId = Annotated[str, Path(min_length=1, max_length=128, pattern=NO_NULL_BYTES)]


@router.get("/search", response_model=DocumentSearchResponse)
def search_documents(
    q: SearchTerm = None,
    status: str | None = Query(default=None, max_length=32, pattern=NO_NULL_BYTES),
    mime_type: str | None = Query(default=None, max_length=128, pattern=NO_NULL_BYTES),
    source: str | None = Query(default=None, max_length=64, pattern=NO_NULL_BYTES),
    limit: PageLimit = 20,
    offset: PageOffset = 0,
    sort: str = Query(default="created_desc", max_length=32, pattern=NO_NULL_BYTES),
    use_case: SearchDocuments = Depends(get_search_documents),
) -> DocumentSearchResponse:
    result = use_case.execute(
        query=q,
        status=status,
        mime_type=mime_type,
        source=source,
        limit=limit,
        offset=offset,
        sort=sort,
    )
    return _search_response(result)


@router.get("/{document_id}", response_model=DocumentSummaryResponse)
def document_detail(
    document_id: DocumentId,
    use_case: GetDocumentDetail = Depends(get_document_detail),
) -> DocumentSummaryResponse:
    return _document_response(use_case.execute(document_id))


@router.get("/{document_id}/chunks", response_model=DocumentChunksResponse)
def document_chunks(
    document_id: DocumentId,
    q: SearchTerm = None,
    limit: PageLimit = 20,
    offset: PageOffset = 0,
    use_case: GetDocumentChunks = Depends(get_document_chunks),
) -> DocumentChunksResponse:
    chunks, total = use_case.execute(document_id=document_id, query=q, limit=limit, offset=offset)
    return DocumentChunksResponse(
        items=[_chunk_response(chunk) for chunk in chunks],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/chat-selection", response_model=ChatSelectionResponse)
def chat_selection(
    payload: ChatSelectionRequest,
    use_case: BuildChatContext = Depends(get_build_chat_context),
) -> ChatSelectionResponse:
    return _chat_selection_response(use_case.execute(payload.document_ids, payload.session_id))


def _search_response(result: DocumentSearchResult) -> DocumentSearchResponse:
    return DocumentSearchResponse(
        items=[_document_response(document) for document in result.items],
        total=result.total,
        limit=result.limit,
        offset=result.offset,
    )


def _document_response(document: DocumentSummary) -> DocumentSummaryResponse:
    return DocumentSummaryResponse(
        document_id=document.document_id,
        filename=document.filename,
        mime_type=document.mime_type,
        status=document.status,
        metadata=document.metadata,
        chunk_count=document.chunk_count,
        created_at=document.created_at,
        updated_at=document.updated_at,
        processed_at=document.processed_at,
        processing_error=document.processing_error,
        snippet=document.snippet,
    )


def _chunk_response(chunk: DocumentChunk) -> DocumentChunkResponse:
    return DocumentChunkResponse(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        chunk_index=chunk.chunk_index,
        content=chunk.content,
        metadata=chunk.metadata,
        created_at=chunk.created_at,
    )


def _chat_selection_response(selection: ChatDocumentSelection) -> ChatSelectionResponse:
    return ChatSelectionResponse(
        session_id=selection.session_id,
        documents=[_document_response(document) for document in selection.documents],
        suggested_prompt=selection.suggested_prompt,
    )
