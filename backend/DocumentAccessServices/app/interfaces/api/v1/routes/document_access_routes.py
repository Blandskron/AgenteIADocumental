from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from app.application.documents.use_cases.delete_document import DeleteDocument
from app.application.documents.use_cases.get_document_content import GetDocumentContent
from app.application.documents.use_cases.get_document_file import GetDocumentFile
from app.domain.documents import DocumentContent, DocumentDeleteResult
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
)

router = APIRouter()


@router.get("/assigned-to-me", response_model=list[DocumentAssignmentResponse])
def assigned_to_me(
    repository: DocumentAccessRepositoryPg = Depends(get_document_access_repository),
) -> list[DocumentAssignmentResponse]:
    return [_assignment_response(assignment) for assignment in repository.list_assigned_to_me()]


@router.get("/managed-by-me", response_model=list[DocumentAssignmentResponse])
def managed_by_me(
    repository: DocumentAccessRepositoryPg = Depends(get_document_access_repository),
) -> list[DocumentAssignmentResponse]:
    return [_assignment_response(assignment) for assignment in repository.list_managed_by_me()]


@router.get("/notifications", response_model=list[NotificationResponse])
def list_notifications(
    status: str | None = None,
    repository: DocumentAccessRepositoryPg = Depends(get_document_access_repository),
) -> list[NotificationResponse]:
    return [_notification_response(notification) for notification in repository.list_notifications(status=status)]


@router.post("/notifications/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: str,
    repository: DocumentAccessRepositoryPg = Depends(get_document_access_repository),
) -> NotificationResponse:
    return _notification_response(repository.mark_notification_read(notification_id))


@router.post("/assignments/{assignment_id}/accept", response_model=DocumentAssignmentResponse)
def accept_assignment(
    assignment_id: str,
    payload: DocumentAssignmentActionRequest | None = None,
    repository: DocumentAccessRepositoryPg = Depends(get_document_access_repository),
) -> DocumentAssignmentResponse:
    return _assignment_response(repository.update_assignment_status(assignment_id, "ACCEPTED", reason=payload.reason if payload else None))


@router.post("/assignments/{assignment_id}/reject", response_model=DocumentAssignmentResponse)
def reject_assignment(
    assignment_id: str,
    payload: DocumentAssignmentActionRequest,
    repository: DocumentAccessRepositoryPg = Depends(get_document_access_repository),
) -> DocumentAssignmentResponse:
    return _assignment_response(repository.update_assignment_status(assignment_id, "REJECTED", reason=payload.reason))


@router.post("/assignments/{assignment_id}/sign", response_model=DocumentAssignmentResponse)
def sign_assignment(
    assignment_id: str,
    payload: DocumentAssignmentActionRequest,
    repository: DocumentAccessRepositoryPg = Depends(get_document_access_repository),
) -> DocumentAssignmentResponse:
    return _assignment_response(repository.update_assignment_status(assignment_id, "SIGNED", signature_value=payload.signature_value))


@router.post("/assignments/{assignment_id}/cancel", response_model=DocumentAssignmentResponse)
def cancel_assignment(
    assignment_id: str,
    payload: DocumentAssignmentActionRequest | None = None,
    repository: DocumentAccessRepositoryPg = Depends(get_document_access_repository),
) -> DocumentAssignmentResponse:
    return _assignment_response(repository.cancel_assignment(assignment_id, reason=payload.reason if payload else None))


@router.get("/assignments/{assignment_id}/events", response_model=list[DocumentAssignmentEventResponse])
def assignment_events(
    assignment_id: str,
    repository: DocumentAccessRepositoryPg = Depends(get_document_access_repository),
) -> list[DocumentAssignmentEventResponse]:
    return [_assignment_event_response(event) for event in repository.list_assignment_events(assignment_id)]


@router.post("/{document_id}/assignments", response_model=DocumentAssignmentResponse)
def assign_document(
    document_id: str,
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
    document_id: str,
    use_case: GetDocumentFile = Depends(get_document_file),
) -> FileResponse:
    document, path = use_case.execute(document_id)
    return FileResponse(
        path=path,
        media_type=document.mime_type,
        filename=document.filename,
        content_disposition_type="inline",
    )


@router.get("/{document_id}/download")
def download_document(
    document_id: str,
    use_case: GetDocumentFile = Depends(get_document_file),
) -> FileResponse:
    document, path = use_case.execute(document_id, for_download=True)
    return FileResponse(
        path=path,
        media_type=document.mime_type,
        filename=document.filename,
        content_disposition_type="attachment",
    )


@router.get("/{document_id}/content", response_model=DocumentContentResponse)
def document_content(
    document_id: str,
    max_chunks: int = Query(default=500, ge=1, le=2000),
    use_case: GetDocumentContent = Depends(get_document_content),
) -> DocumentContentResponse:
    return _content_response(use_case.execute(document_id=document_id, max_chunks=max_chunks))


@router.delete("/{document_id}", response_model=DocumentDeleteResponse)
def delete_document(
    document_id: str,
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
