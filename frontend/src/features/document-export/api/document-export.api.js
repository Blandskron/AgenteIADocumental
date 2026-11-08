function normalizeExport(payload = {}) {
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

export async function createChatMessagePdf(apiClient, payload) {
  const response = await apiClient("/api/v1/exports/chat-message/pdf", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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

export function downloadExport(apiClient, exportId) {
  return apiClient(`/api/v1/exports/${exportId}/download`, {
    method: "GET",
    responseType: "blob",
  });
}
