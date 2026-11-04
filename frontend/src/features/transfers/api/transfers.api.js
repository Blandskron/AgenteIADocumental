function normalizeTransfer(transfer = {}) {
  return {
    transferId: transfer.transfer_id,
    ownerUserId: transfer.owner_user_id || "",
    documentId: transfer.document_id || null,
    filename: transfer.filename || "archivo",
    direction: transfer.direction || "UPLOAD",
    status: transfer.status || "PENDING",
    progress: Number(transfer.progress || 0),
    sizeBytes: transfer.size_bytes ?? null,
    metadata: transfer.metadata || {},
    createdAt: transfer.created_at || "",
    updatedAt: transfer.updated_at || "",
  };
}

export function listTransfers(apiClient, limit = 50) {
  return apiClient(`/api/v1/transfers?limit=${limit}`, {
    method: "GET",
  }).then((payload) => (Array.isArray(payload) ? payload.map(normalizeTransfer) : []));
}

export function createTransfer(apiClient, payload) {
  return apiClient("/api/v1/transfers", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).then(normalizeTransfer);
}

export function updateTransfer(apiClient, transferId, payload) {
  return apiClient(`/api/v1/transfers/${transferId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).then(normalizeTransfer);
}

export function clearTransferHistory(apiClient) {
  return apiClient("/api/v1/transfers/history", {
    method: "DELETE",
  });
}
