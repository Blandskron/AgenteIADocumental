import type { DocumentItem } from "@/entities/document/model/types.ts";
import type { TransferJournal } from "./tracked-transfer.ts";
import { runDocumentTransfer } from "./tracked-transfer.ts";

export function runDocumentUpload({
  transfers,
  file,
  conversationId,
  upload,
  poll,
  isProcessed,
}: {
  transfers: TransferJournal;
  file: File;
  conversationId?: string;
  upload: () => Promise<DocumentItem>;
  poll: (id: string) => Promise<DocumentItem>;
  isProcessed: (status: string) => boolean;
}) {
  return runDocumentTransfer({
    transfers,
    initial: {
      filename: file.name,
      direction: "UPLOAD",
      status: "RUNNING",
      progress: 15,
      size_bytes: file.size,
      ...(conversationId !== undefined
        ? { metadata: { conversation_id: conversationId } }
        : {}),
    },
    operation: async (report) => {
      const document = await upload();
      if (isProcessed(document.status)) return document;
      report({
        document_id: document.documentId,
        progress: 65,
        status: "RUNNING",
      });
      return poll(document.documentId);
    },
  });
}

export function runDocumentDownload({
  transfers,
  document,
  download,
}: {
  transfers: TransferJournal;
  document: DocumentItem;
  download: () => Promise<void>;
}) {
  return runDocumentTransfer({
    transfers,
    operation: download,
    initial: {
      filename: document.filename,
      direction: "DOWNLOAD",
      status: "RUNNING",
      progress: 40,
      document_id: document.documentId,
    },
  });
}
