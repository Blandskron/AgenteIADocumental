function normalizeExport(payload = {}) {
  if (typeof payload.export_id !== "string" || !/^[A-Za-z0-9_-]{1,128}$/.test(payload.export_id)) {
    throw new Error("El servicio devolvió un PDF sin identificador válido.");
  }
  return {
    exportId: payload.export_id,
    sourceType: payload.source_type,
    sourceId: payload.source_id,
    conversationId: payload.conversation_id,
    messageId: payload.message_id,
    title: payload.title,
    format: payload.format,
    status: payload.status,
    filename: payload.filename,
    mimeType: payload.mime_type,
    fileSizeBytes: payload.file_size_bytes,
    metadata: payload.metadata || {},
    downloadUrl: payload.download_url,
    createdAt: payload.created_at,
    updatedAt: payload.updated_at,
    expiresAt: payload.expires_at,
    sha256: payload.sha256,
  };
}

function normalizeSource(source = {}) {
  const score = Number(source.score ?? 0);
  const pageValue = source.page ?? source.pageNumber ?? source.page_number;
  const page = pageValue == null ? null : Number(pageValue);
  if (!Number.isFinite(score) || (page !== null && (!Number.isInteger(page) || page < 1))) {
    throw new Error("La fuente contiene una página o puntuación no válida.");
  }
  return {
    document_id: source.documentId || source.document_id || "",
    chunk_id: source.chunkId || source.chunk_id || "",
    filename: source.filename || "",
    content: source.content || "",
    score,
    page,
    snippet: source.snippet || "",
  };
}

export function exportReferences(conversationId, messageId) {
  const persisted = (id) => typeof id === "string" && id.length > 0
    && !id.startsWith("local-") && !id.startsWith("blandskron-");
  const conversation = persisted(conversationId) ? conversationId : null;
  return {
    conversation_id: conversation,
    message_id: conversation && persisted(messageId) ? messageId : null,
  };
}

export async function createChatMessagePdf(apiClient, payload, { signal, operationKey } = {}) {
  const response = await apiClient("/api/v1/exports/chat-message/pdf", {
    method: "POST",
    signal,
    headers: { "Content-Type": "application/json", ...(operationKey ? { "Idempotency-Key": operationKey } : {}) },
    body: JSON.stringify({
      ...exportReferences(payload.conversationId, payload.messageId),
      title: payload.title || "Respuesta documental",
      question: payload.question || "",
      answer: payload.answer,
      sources: (payload.sources || []).map(normalizeSource),
      metadata: payload.metadata || {},
    }),
  });

  return normalizeExport(response);
}

export function downloadExport(apiClient, exportId, signal) {
  return apiClient(`/api/v1/exports/${encodeURIComponent(exportId)}/download`, {
    method: "GET",
    responseType: "blob", signal, cache: "no-store",
  });
}

export async function listExports(apiClient, { before, signal } = {}) {
  const query = new URLSearchParams({ limit: "20" });
  if (before) query.set("before", before);
  const data = await apiClient(`/api/v1/exports?${query}`, { method: "GET", signal, cache: "no-store" });
  if (!data || !Array.isArray(data.items) || data.items.length > 20
      || !(data.next_cursor === null || (typeof data.next_cursor === "string" && data.next_cursor.length > 0 && data.next_cursor.length <= 512))) {
    throw new Error("El historial PDF devolvió un formato no válido.");
  }
  return { items: data.items.map(normalizeExport), nextCursor: data.next_cursor };
}

export function deleteExport(apiClient, exportId, signal) {
  return apiClient(`/api/v1/exports/${encodeURIComponent(exportId)}`, { method: "DELETE", signal });
}
