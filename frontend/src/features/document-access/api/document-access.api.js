function readFilenameFromDisposition(contentDisposition, fallback) {
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

export async function getDocumentPreview(apiClient, document) {
  const response = await apiClient(`/api/v1/documents/${document.documentId}/preview`, {
    method: "GET",
    responseType: "blob",
  });

  return {
    url: URL.createObjectURL(response.blob),
    contentType: response.contentType,
    filename: readFilenameFromDisposition(response.contentDisposition, document.filename),
  };
}

export async function downloadDocument(apiClient, document) {
  const response = await apiClient(`/api/v1/documents/${document.documentId}/download`, {
    method: "GET",
    responseType: "blob",
  });
  const filename = readFilenameFromDisposition(response.contentDisposition, document.filename);
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

export function getDocumentContent(apiClient, documentId) {
  return apiClient(`/api/v1/documents/${documentId}/content`, {
    method: "GET",
  });
}

export function deleteDocument(apiClient, documentId) {
  return apiClient(`/api/v1/documents/${documentId}`, {
    method: "DELETE",
  });
}

export function listAssignedToMe(apiClient, offset = 0) {
  return listPage(apiClient, "assigned-to-me", offset, normalizeAssignment);
}

export function listManagedByMe(apiClient, offset = 0) {
  return listPage(apiClient, "managed-by-me", offset, normalizeAssignment);
}

export function listNotifications(apiClient, offset = 0) {
  return listPage(apiClient, "notifications", offset, normalizeNotification);
}

async function listPage(apiClient, path, offset, normalize) {
  const payload = await apiClient(`/api/v1/documents/${path}?limit=50&offset=${offset}`, { method: "GET" });
  return { items: payload.items.map(normalize), hasMore: payload.has_more,
    nextOffset: payload.offset + payload.items.length };
}

export function markNotificationRead(apiClient, notificationId) {
  return apiClient(`/api/v1/documents/notifications/${notificationId}/read`, { method: "POST" }).then(normalizeNotification);
}

export function assignDocument(apiClient, documentId, payload) {
  return apiClient(`/api/v1/documents/${documentId}/assignments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      assigned_to_user_id: String(payload.userId),
      allow_download: payload.allowDownload !== false,
      due_at: payload.dueAt ? new Date(payload.dueAt).toISOString() : null,
      metadata: payload.metadata || {},
    }),
  }).then(normalizeAssignment);
}

export function acceptAssignment(apiClient, assignmentId, reason = "") {
  return updateAssignmentAction(apiClient, assignmentId, "accept", { reason });
}

export function rejectAssignment(apiClient, assignmentId, reason = "") {
  return updateAssignmentAction(apiClient, assignmentId, "reject", { reason });
}

export function signAssignment(apiClient, assignmentId, signatureValue = "") {
  return updateAssignmentAction(apiClient, assignmentId, "sign", { signature_value: signatureValue });
}

export function cancelAssignment(apiClient, assignmentId, reason = "") {
  return updateAssignmentAction(apiClient, assignmentId, "cancel", { reason });
}

function updateAssignmentAction(apiClient, assignmentId, action, payload) {
  return apiClient(`/api/v1/documents/assignments/${assignmentId}/${action}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).then(normalizeAssignment);
}

function normalizeAssignment(assignment = {}) {
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

function normalizeNotification(notification = {}) {
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
