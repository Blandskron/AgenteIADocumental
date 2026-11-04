function normalizeSource(source = {}) {
  return {
    documentId: source.document_id,
    chunkId: source.chunk_id,
    content: source.content || "",
    score: Number(source.score || 0),
    filename: source.filename || null,
  };
}

function normalizeChatAskResponse(payload = {}) {
  return {
    answer: payload.answer || "",
    sources: Array.isArray(payload.sources) ? payload.sources.map(normalizeSource) : [],
  };
}

export function askExistingDocuments(apiClient, { question, sessionId, documentIds = [] }) {
  return apiClient("/api/v1/chat/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, session_id: sessionId, document_ids: documentIds }),
  }).then(normalizeChatAskResponse);
}
