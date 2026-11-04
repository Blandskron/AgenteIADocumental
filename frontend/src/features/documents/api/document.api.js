import { createDocumentMetadata } from "../../../entities/document/model/document-metadata.factory";

function normalizeDocument(payload = {}) {
  return {
    documentId: payload.document_id,
    filename: payload.filename || "documento",
    status: payload.status || "UNKNOWN",
    mimeType: payload.mime_type || "",
    storagePath: payload.storage_path || "",
    metadata: payload.metadata || {},
  };
}

export function uploadDocument(apiClient, { file, conversationId }) {
  const form = new FormData();
  form.append("file", file);
  form.append("metadata", JSON.stringify(createDocumentMetadata(conversationId)));
  form.append("process", "true");

  return apiClient("/api/v1/documents/upload", {
    method: "POST",
    body: form,
  }).then(normalizeDocument);
}

export function getDocumentStatus(apiClient, documentId) {
  return apiClient(`/api/v1/documents/${documentId}/status`, {
    method: "GET",
  }).then(normalizeDocument);
}
