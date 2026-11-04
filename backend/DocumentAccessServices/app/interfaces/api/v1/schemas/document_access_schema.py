from pydantic import BaseModel, Field
from datetime import datetime


class DocumentContentResponse(BaseModel):
    document_id: str
    filename: str
    content: str
    chunk_count: int


class DocumentDeleteResponse(BaseModel):
    document_id: str
    filename: str
    deleted: bool
    file_deleted: bool


class DocumentAssignmentCreateRequest(BaseModel):
    assigned_to_user_id: str
    allow_download: bool = True
    due_at: datetime | None = None
    metadata: dict = Field(default_factory=dict)


class DocumentAssignmentActionRequest(BaseModel):
    reason: str | None = None
    signature_value: str | None = None


class DocumentAssignmentResponse(BaseModel):
    assignment_id: str
    document_id: str
    tenant_id: str
    assigned_to_user_id: str
    assigned_by_user_id: str
    assigned_by_role: str | None = None
    status: str
    rejection_reason: str | None = None
    signature_value: str | None = None
    signed_at: datetime | None = None
    due_at: datetime | None = None
    allow_download: bool = True
    metadata: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class DocumentAssignmentEventResponse(BaseModel):
    event_id: str
    assignment_id: str
    actor_user_id: str
    action: str
    reason: str | None = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime


class NotificationResponse(BaseModel):
    notification_id: str
    tenant_id: str | None = None
    recipient_user_id: str
    actor_user_id: str | None = None
    document_id: str | None = None
    assignment_id: str | None = None
    type: str
    title: str
    body: str
    status: str
    metadata: dict = Field(default_factory=dict)
    read_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
