import { runDocumentTransfer } from "./tracked-transfer.js";

export function runDocumentUpload({ transfers, file, conversationId, upload, poll, isProcessed }) {
  return runDocumentTransfer({
    transfers,
    initial: { filename: file.name, direction: "UPLOAD", status: "RUNNING", progress: 15, size_bytes: file.size,
      ...(conversationId !== undefined ? { metadata: { conversation_id: conversationId } } : {}) },
    operation: async (report) => {
      const document = await upload();
      if (isProcessed(document.status)) return document;
      report({ document_id: document.documentId, progress: 65, status: "RUNNING" });
      return poll(document.documentId);
    },
  });
}

export function runDocumentDownload({ transfers, document, download }) {
  return runDocumentTransfer({ transfers, operation: download,
    initial: { filename: document.filename, direction: "DOWNLOAD", status: "RUNNING", progress: 40, document_id: document.documentId } });
}
