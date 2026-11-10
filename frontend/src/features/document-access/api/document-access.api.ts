import type { DocumentItem } from "@/entities/document/model/types.ts";
import type { MaybeClient } from "@/shared/api/types.ts";
import { requireClient } from "@/shared/api/types.ts";
export type Assignment = ReturnType<typeof normalizeAssignment>;
export type Notification = ReturnType<typeof normalizeNotification>;
interface AssignmentDto {
  assignment_id?: string;
  document_id?: string;
  tenant_id?: string;
  assigned_to_user_id?: string;
  assigned_by_user_id?: string;
  assigned_by_role?: string;
  status?: string;
  rejection_reason?: string;
  signature_value?: string;
  signed_at?: string;
  due_at?: string;
  allow_download?: boolean;
  metadata?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
}
interface NotificationDto {
  notification_id?: string;
  tenant_id?: string;
  recipient_user_id?: string;
  actor_user_id?: string;
  document_id?: string;
  assignment_id?: string;
  type?: string;
  title?: string;
  body?: string;
  status?: string;
  metadata?: Record<string, unknown>;
  read_at?: string;
  created_at?: string;
}
function readFilenameFromDisposition(
  contentDisposition: string,
  fallback: string,
) {
  const disposition = contentDisposition || "";
  const extended = /(?:^|;)\s*filename\*=utf-8''([^;]+)/i.exec(disposition);
  if (extended) {
    try {
      return decodeURIComponent(extended[1].trim()) || fallback;
    } catch {
      // Use the legacy filename field when the extended value is malformed.
    }
  }
  const match = /(?:^|;)\s*filename=(?:"([^"]*)"|([^;]*))/i.exec(disposition);
  return match?.[1] || match?.[2]?.trim() || fallback;
}

export async function getDocumentPreview(
  apiClient: MaybeClient,
  document: DocumentItem,
) {
  const response = await requireClient(apiClient)(
    `/api/v1/documents/${document.documentId}/preview`,
    {
      method: "GET",
      responseType: "blob",
    },
  );

  return {
    url: URL.createObjectURL(response.blob),
    contentType: response.contentType,
    filename: readFilenameFromDisposition(
      response.contentDisposition,
      document.filename,
    ),
  };
}

export async function downloadDocument(
  apiClient: MaybeClient,
  document: DocumentItem,
) {
  const response = await requireClient(apiClient)(
    `/api/v1/documents/${document.documentId}/download`,
    {
      method: "GET",
      responseType: "blob",
    },
  );
  const filename = readFilenameFromDisposition(
    response.contentDisposition,
    document.filename,
  );
  const url = URL.createObjectURL(response.blob);
  const anchor = documentNode().createElement("a");

  anchor.href = url;
  anchor.download = filename;
  anchor.style.display = "none";
  documentNode().body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function getDocumentContent(apiClient: MaybeClient, documentId: string) {
  return requireClient(apiClient)(`/api/v1/documents/${documentId}/content`, {
    method: "GET",
  });
}

export function deleteDocument(apiClient: MaybeClient, documentId: string) {
  return requireClient(apiClient)(`/api/v1/documents/${documentId}`, {
    method: "DELETE",
  });
}

export function listAssignedToMe(apiClient: MaybeClient, offset: number = 0) {
  return listPage(apiClient, "assigned-to-me", offset, normalizeAssignment);
}

export function listManagedByMe(apiClient: MaybeClient, offset: number = 0) {
  return listPage(apiClient, "managed-by-me", offset, normalizeAssignment);
}

export function listNotifications(apiClient: MaybeClient, offset: number = 0) {
  return listPage(apiClient, "notifications", offset, normalizeNotification);
}

async function listPage<T, R>(
  apiClient: MaybeClient,
  path: string,
  offset: number,
  normalize: (item: T) => R,
) {
  const payload = await requireClient(apiClient)<{
    items: T[];
    has_more: boolean;
    offset: number;
  }>(`/api/v1/documents/${path}?limit=50&offset=${offset}`, { method: "GET" });
  return {
    items: payload.items.map(normalize),
    hasMore: payload.has_more,
    nextOffset: payload.offset + payload.items.length,
  };
}

export function markNotificationRead(
  apiClient: MaybeClient,
  notificationId: string,
) {
  return requireClient(apiClient)<Parameters<typeof normalizeNotification>[0]>(
    `/api/v1/documents/notifications/${notificationId}/read`,
    { method: "POST" },
  ).then(normalizeNotification);
}

export function assignDocument(
  apiClient: MaybeClient,
  documentId: string,
  payload: {
    userId: string;
    allowDownload?: boolean;
    dueAt?: string;
    metadata?: Record<string, unknown>;
  },
) {
  return requireClient(apiClient)<Parameters<typeof normalizeAssignment>[0]>(
    `/api/v1/documents/${documentId}/assignments`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        assigned_to_user_id: String(payload.userId),
        allow_download: payload.allowDownload !== false,
        due_at: payload.dueAt ? new Date(payload.dueAt).toISOString() : null,
        metadata: payload.metadata || {},
      }),
    },
  ).then(normalizeAssignment);
}

export function acceptAssignment(
  apiClient: MaybeClient,
  assignmentId: string,
  reason: string = "",
) {
  return updateAssignmentAction(apiClient, assignmentId, "accept", { reason });
}

export function rejectAssignment(
  apiClient: MaybeClient,
  assignmentId: string,
  reason: string = "",
) {
  return updateAssignmentAction(apiClient, assignmentId, "reject", { reason });
}

export function signAssignment(
  apiClient: MaybeClient,
  assignmentId: string,
  signatureValue: string = "",
) {
  return updateAssignmentAction(apiClient, assignmentId, "sign", {
    signature_value: signatureValue,
  });
}

export function cancelAssignment(
  apiClient: MaybeClient,
  assignmentId: string,
  reason: string = "",
) {
  return updateAssignmentAction(apiClient, assignmentId, "cancel", { reason });
}

function updateAssignmentAction(
  apiClient: MaybeClient,
  assignmentId: string,
  action: string,
  payload: Record<string, unknown>,
) {
  return requireClient(apiClient)<Parameters<typeof normalizeAssignment>[0]>(
    `/api/v1/documents/assignments/${assignmentId}/${action}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  ).then(normalizeAssignment);
}

function normalizeAssignment(assignment: AssignmentDto = {}) {
  return {
    assignmentId: assignment.assignment_id || "",
    documentId: assignment.document_id || "",
    tenantId: assignment.tenant_id || "",
    assignedToUserId: String(assignment.assigned_to_user_id || ""),
    assignedByUserId: String(assignment.assigned_by_user_id || ""),
    assignedByRole: assignment.assigned_by_role || "",
    status: assignment.status || "PENDING",
    rejectionReason: assignment.rejection_reason || "",
    signatureValue: assignment.signature_value || "",
    signedAt: assignment.signed_at || "",
    dueAt: assignment.due_at || "",
    allowDownload: assignment.allow_download !== false,
    metadata: assignment.metadata || {},
    createdAt: assignment.created_at || "",
    updatedAt: assignment.updated_at || "",
  };
}

function normalizeNotification(notification: NotificationDto = {}) {
  return {
    notificationId: notification.notification_id || "",
    tenantId: notification.tenant_id || "",
    recipientUserId: String(notification.recipient_user_id || ""),
    actorUserId: String(notification.actor_user_id || ""),
    documentId: notification.document_id || "",
    assignmentId: notification.assignment_id || "",
    type: notification.type || "",
    title: notification.title || "Notificacion",
    body: notification.body || "",
    status: notification.status || "UNREAD",
    metadata: notification.metadata || {},
    readAt: notification.read_at || "",
    createdAt: notification.created_at || "",
  };
}

function documentNode() {
  return window.document;
}
