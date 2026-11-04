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
  return {
    document_id: source.documentId || source.document_id || "",
    chunk_id: source.chunkId || source.chunk_id || "",
    filename: source.filename || "",
    content: source.content || "",
    score: Number(source.score || 0),
  };
}

export async function createChatMessagePdf(apiClient, payload) {
  const response = await apiClient("/api/v1/exports/chat-message/pdf", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      conversation_id: payload.conversationId || null,
      message_id: payload.messageId || null,
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
