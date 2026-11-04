function normalizeDocument(document = {}) {
  return {
    documentId: document.document_id,
    filename: document.filename || "documento",
    mimeType: document.mime_type || "",
    status: document.status || "UNKNOWN",
    metadata: document.metadata || {},
    chunkCount: Number(document.chunk_count || 0),
    createdAt: document.created_at || "",
    updatedAt: document.updated_at || "",
    processedAt: document.processed_at || null,
    processingError: document.processing_error || null,
    snippet: document.snippet || "",
  };
}

function normalizeSearchResponse(payload = {}) {
  return {
    items: Array.isArray(payload.items) ? payload.items.map(normalizeDocument) : [],
    total: Number(payload.total || 0),
    limit: Number(payload.limit || 20),
    offset: Number(payload.offset || 0),
  };
}

function normalizeChatSelection(payload = {}) {
  return {
    sessionId: payload.session_id || null,
    documents: Array.isArray(payload.documents) ? payload.documents.map(normalizeDocument) : [],
    suggestedPrompt: payload.suggested_prompt || "",
  };
}

export function searchDocuments(apiClient, filters = {}) {
  const params = new URLSearchParams();
  if (filters.query) params.set("q", filters.query);
  if (filters.status) params.set("status", filters.status);
  if (filters.mimeType) params.set("mime_type", filters.mimeType);
  if (filters.source) params.set("source", filters.source);
  params.set("limit", String(filters.limit || 20));
  params.set("offset", String(filters.offset || 0));
  params.set("sort", filters.sort || "created_desc");

  return apiClient(`/api/v1/documents/search?${params.toString()}`, {
    method: "GET",
  }).then(normalizeSearchResponse);
}

export function buildChatSelection(apiClient, { documentIds, sessionId }) {
  return apiClient("/api/v1/documents/chat-selection", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_ids: documentIds, session_id: sessionId }),
  }).then(normalizeChatSelection);
}
