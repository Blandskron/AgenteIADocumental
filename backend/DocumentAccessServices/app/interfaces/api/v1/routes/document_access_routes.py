import re
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from app.application.documents.use_cases.delete_document import DeleteDocument
from app.application.documents.use_cases.get_document_content import GetDocumentContent
from app.application.documents.use_cases.get_document_file import GetDocumentFile
from app.domain.documents import DocumentContent, DocumentDeleteResult, DocumentFile
from app.shared.constants import INLINE_MIME_TYPES, MAX_CONTENT_CHUNKS, SUPPORTED_MIME_TYPES
from app.infrastructure.database.repositories import DocumentAccessRepositoryPg
from app.interfaces.api.v1.dependencies import (
    get_delete_document,
    get_document_access_repository,
    get_document_content,
    get_document_file,
)
from app.interfaces.api.v1.schemas.document_access_schema import (
    DocumentAssignmentActionRequest,
    DocumentAssignmentCreateRequest,
    DocumentAssignmentEventResponse,
    DocumentAssignmentResponse,
    DocumentContentResponse,
    DocumentDeleteResponse,
    NotificationResponse,
    NotificationStatus,
    Identifier,
    Page,
)

router = APIRouter()
PageLimit = Annotated[int, Query(ge=1, le=100)]
PageOffset = Annotated[int, Query(ge=0, le=100_000)]


def _page(rows, converter, limit, offset):
    return {"items": [converter(row) for row in rows[:limit]], "limit": limit,
            "offset": offset, "has_more": len(rows) > limit}


@router.get("/assigned-to-me", response_model=Page[DocumentAssignmentResponse])
def assigned_to_me(
    limit: PageLimit = 50,
    offset: PageOffset = 0,
    repository: DocumentAccessRepositoryPg = Depends(get_document_access_repository),
):
    return _page(repository.list_assigned_to_me(limit + 1, offset), _assignment_response, limit, offset)


@router.get("/managed-by-me", response_model=Page[DocumentAssignmentResponse])
def managed_by_me(
    limit: PageLimit = 50,
    offset: PageOffset = 0,
    repository: DocumentAccessRepositoryPg = Depends(get_document_access_repository),
):
    return _page(repository.list_managed_by_me(limit + 1, offset), _assignment_response, limit, offset)


@router.get("/notifications", response_model=Page[NotificationResponse])
def list_notifications(
    status: NotificationStatus | None = None,
    limit: PageLimit = 50,
    offset: PageOffset = 0,
    repository: DocumentAccessRepositoryPg = Depends(get_document_access_repository),
):
    rows = repository.list_notifications(status=status, limit=limit + 1, offset=offset)
    return _page(rows, _notification_response, limit, offset)


@router.post("/notifications/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: Identifier,
    repository: DocumentAccessRepositoryPg = Depends(get_document_access_repository),
) -> NotificationResponse:
    return _notification_response(repository.mark_notification_read(notification_id))


@router.post("/assignments/{assignment_id}/accept", response_model=DocumentAssignmentResponse)
def accept_assignment(
    assignment_id: Identifier,
    payload: DocumentAssignmentActionRequest | None = None,
    repository: DocumentAccessRepositoryPg = Depends(get_document_access_repository),
) -> DocumentAssignmentResponse:
    return _assignment_response(repository.update_assignment_status(assignment_id, "ACCEPTED", reason=payload.reason if payload else None))


@router.post("/assignments/{assignment_id}/reject", response_model=DocumentAssignmentResponse)
def reject_assignment(
    assignment_id: Identifier,
    payload: DocumentAssignmentActionRequest,
    repository: DocumentAccessRepositoryPg = Depends(get_document_access_repository),
) -> DocumentAssignmentResponse:
    return _assignment_response(repository.update_assignment_status(assignment_id, "REJECTED", reason=payload.reason))


@router.post("/assignments/{assignment_id}/sign", response_model=DocumentAssignmentResponse)
def sign_assignment(
    assignment_id: Identifier,
    payload: DocumentAssignmentActionRequest,
    repository: DocumentAccessRepositoryPg = Depends(get_document_access_repository),
) -> DocumentAssignmentResponse:
    return _assignment_response(repository.update_assignment_status(assignment_id, "SIGNED", signature_value=payload.signature_value))


@router.post("/assignments/{assignment_id}/cancel", response_model=DocumentAssignmentResponse)
def cancel_assignment(
    assignment_id: Identifier,
    payload: DocumentAssignmentActionRequest | None = None,
    repository: DocumentAccessRepositoryPg = Depends(get_document_access_repository),
) -> DocumentAssignmentResponse:
    return _assignment_response(repository.cancel_assignment(assignment_id, reason=payload.reason if payload else None))


@router.get("/assignments/{assignment_id}/events", response_model=Page[DocumentAssignmentEventResponse])
def assignment_events(
    assignment_id: Identifier,
    limit: PageLimit = 50,
    offset: PageOffset = 0,
    repository: DocumentAccessRepositoryPg = Depends(get_document_access_repository),
):
    rows = repository.list_assignment_events(assignment_id, limit + 1, offset)
    if rows is None:
        raise HTTPException(status_code=404, detail="Assignment not found.")
    return _page(rows, _assignment_event_response, limit, offset)


@router.post("/{document_id}/assignments", response_model=DocumentAssignmentResponse)
def assign_document(
    document_id: Identifier,
    payload: DocumentAssignmentCreateRequest,
    repository: DocumentAccessRepositoryPg = Depends(get_document_access_repository),
) -> DocumentAssignmentResponse:
    return _assignment_response(
        repository.create_assignment(
            document_id=document_id,
            assigned_to_user_id=payload.assigned_to_user_id,
            allow_download=payload.allow_download,
            due_at=payload.due_at,
            metadata=payload.metadata,
        )
    )


@router.get("/{document_id}/preview")
def preview_document(
    document_id: Identifier,
    use_case: GetDocumentFile = Depends(get_document_file),
) -> FileResponse:
    document, path = use_case.execute(document_id)
    return _file_response(document, path)


@router.get("/{document_id}/download")
def download_document(
    document_id: Identifier,
    use_case: GetDocumentFile = Depends(get_document_file),
) -> FileResponse:
    document, path = use_case.execute(document_id, for_download=True)
    return _file_response(document, path, for_download=True)


def _file_response(document: DocumentFile, path: Path, for_download: bool = False) -> FileResponse:
    mime_type = document.mime_type.split(";", 1)[0].strip().lower()
    if not for_download and mime_type not in INLINE_MIME_TYPES:
        raise HTTPException(status_code=415, detail="Document type does not support preview.")
    if mime_type not in SUPPORTED_MIME_TYPES:
        mime_type = "application/octet-stream"
    filename = document.filename.replace("\\", "/").rsplit("/", 1)[-1]
    filename = re.sub(r"[\x00-\x1f\x7f]", "_", filename).strip() or "document"
    return FileResponse(
        path=path,
        media_type=mime_type,
        filename=filename,
        content_disposition_type="attachment" if for_download else "inline",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
    )


@router.get("/{document_id}/content", response_model=DocumentContentResponse)
def document_content(
    document_id: Identifier,
    max_chunks: int = Query(default=500, ge=1, le=MAX_CONTENT_CHUNKS),
    use_case: GetDocumentContent = Depends(get_document_content),
) -> DocumentContentResponse:
    return _content_response(use_case.execute(document_id=document_id, max_chunks=max_chunks))


@router.delete("/{document_id}", response_model=DocumentDeleteResponse)
def delete_document(
    document_id: Identifier,
    use_case: DeleteDocument = Depends(get_delete_document),
) -> DocumentDeleteResponse:
    return _delete_response(use_case.execute(document_id))


def _content_response(content: DocumentContent) -> DocumentContentResponse:
    return DocumentContentResponse(
        document_id=content.document_id,
        filename=content.filename,
        content=content.content,
        chunk_count=content.chunk_count,
    )


def _delete_response(result: DocumentDeleteResult) -> DocumentDeleteResponse:
    return DocumentDeleteResponse(
        document_id=result.document_id,
        filename=result.filename,
        deleted=result.deleted,
        file_deleted=result.file_deleted,
    )


def _assignment_response(assignment) -> DocumentAssignmentResponse:
    if assignment is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Assignment not found.")
    return DocumentAssignmentResponse(
        assignment_id=str(assignment.assignment_id),
        document_id=str(assignment.document_id),
        tenant_id=str(assignment.tenant_id),
        assigned_to_user_id=assignment.assigned_to_user_id,
        assigned_by_user_id=assignment.assigned_by_user_id,
        assigned_by_role=assignment.assigned_by_role,
        status=assignment.status,
        rejection_reason=assignment.rejection_reason,
        signature_value=assignment.signature_value,
        signed_at=assignment.signed_at,
        due_at=assignment.due_at,
        allow_download=assignment.allow_download,
        metadata=assignment.metadata_ or {},
        created_at=assignment.created_at,
        updated_at=assignment.updated_at,
    )


def _assignment_event_response(event) -> DocumentAssignmentEventResponse:
    return DocumentAssignmentEventResponse(
        event_id=str(event.event_id),
        assignment_id=str(event.assignment_id),
        actor_user_id=event.actor_user_id,
        action=event.action,
        reason=event.reason,
        metadata=event.metadata_ or {},
        created_at=event.created_at,
    )


def _notification_response(notification) -> NotificationResponse:
    if notification is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Notification not found.")
    return NotificationResponse(
        notification_id=str(notification.notification_id),
        tenant_id=notification.tenant_id,
        recipient_user_id=notification.recipient_user_id,
        actor_user_id=notification.actor_user_id,
        document_id=notification.document_id,
        assignment_id=notification.assignment_id,
        type=notification.type,
        title=notification.title,
        body=notification.body,
        status=notification.status,
        metadata=notification.metadata_ or {},
        read_at=notification.read_at,
        created_at=notification.created_at,
        updated_at=notification.updated_at,
    )
