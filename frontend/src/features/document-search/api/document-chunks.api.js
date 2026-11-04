export function getDocumentChunks(apiClient, documentId, { limit = 20, offset = 0, q = "" } = {}) {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  if (q) params.set("q", q);
  return apiClient(`/api/v1/documents/${documentId}/chunks?${params.toString()}`, {
    method: "GET",
  }).then((payload) => Array.isArray(payload.items) ? payload.items : []);
}
