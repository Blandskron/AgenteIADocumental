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

export function listTransfers(apiClient, { limit = 50, offset = 0 } = {}) {
  return apiClient(`/api/v1/transfers?limit=${limit}&offset=${offset}`, {
    method: "GET",
  }).then((payload) => {
    if (!payload || !Array.isArray(payload.items) || !Number.isInteger(payload.offset) || payload.offset < 0
      || payload.offset !== offset || payload.limit !== limit || payload.items.length > limit || typeof payload.has_more !== "boolean"
      || payload.items.some((item) => !item || typeof item.transfer_id !== "string" || !item.transfer_id)) {
      throw new Error("Contrato de historial incompatible. Actualiza los servicios y la interfaz juntos.");
    }
    return { items: payload.items.map(normalizeTransfer), hasMore: payload.has_more,
      nextOffset: payload.offset + payload.items.length };
  });
}

export function createTransfer(apiClient, payload) {
  return apiClient("/api/v1/transfers", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).then(normalizeTransfer);
}

export function updateTransfer(apiClient, transferId, payload) {
  return apiClient(`/api/v1/transfers/${encodeURIComponent(transferId)}`, {
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
