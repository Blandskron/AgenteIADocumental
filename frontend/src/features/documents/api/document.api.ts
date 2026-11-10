import { createDocumentMetadata } from "@/entities/document/model/document-metadata.factory";
import type { MaybeClient } from "@/shared/api/types.ts";
import { requireClient } from "@/shared/api/types.ts";
interface DocumentDto {
  document_id?: string;
  filename?: string;
  status?: string;
  mime_type?: string;
  storage_path?: string;
  metadata?: Record<string, unknown>;
}

function normalizeDocument(payload: DocumentDto = {}) {
  return {
    documentId: payload.document_id || "",
    filename: payload.filename || "documento",
    status: payload.status || "UNKNOWN",
    mimeType: payload.mime_type || "",
    storagePath: payload.storage_path || "",
    metadata: payload.metadata || {},
  };
}

export function uploadDocument(
  apiClient: MaybeClient,
  { file, conversationId }: { file: File; conversationId?: string | null },
) {
  const form = new FormData();
  form.append("file", file);
  form.append(
    "metadata",
    JSON.stringify(createDocumentMetadata(conversationId)),
  );
  form.append("process", "true");

  return requireClient(apiClient)<Parameters<typeof normalizeDocument>[0]>(
    "/api/v1/documents/upload",
    {
      method: "POST",
      body: form,
    },
  ).then(normalizeDocument);
}

export function getDocumentStatus(apiClient: MaybeClient, documentId: string) {
  return requireClient(apiClient)<Parameters<typeof normalizeDocument>[0]>(
    `/api/v1/documents/${documentId}/status`,
    {
      method: "GET",
    },
  ).then(normalizeDocument);
}
