import { waitForDocumentProcessed } from "@/features/documents/api/document-status.poller";
import { uploadDocument } from "@/features/documents/api/document.api";
import { isDocumentProcessed } from "@/features/documents/lib/document-status.ts";
import { runDocumentUpload } from "@/features/transfers/document-transfer-flows.ts";
import type { TransferJournal } from "@/features/transfers/tracked-transfer.ts";
import type { MaybeClient } from "@/shared/api/types.ts";

export function useDocumentQuestionFlow({
  documentClient,
  conversationId,
  clearSelectedFile,
  transfers,
}: {
  documentClient: MaybeClient;
  conversationId?: string;
  clearSelectedFile: () => void;
  transfers: TransferJournal;
}) {
  async function uploadAndWait(file: File) {
    const document = await runDocumentUpload({
      transfers,
      file,
      conversationId,
      upload: () => uploadDocument(documentClient, { file, conversationId }),
      poll: (id) => waitForDocumentProcessed(documentClient, id),
      isProcessed: isDocumentProcessed,
    });
    clearSelectedFile();
    return document;
  }
  return { uploadAndWait };
}
