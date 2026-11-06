import { uploadDocument } from "../../documents/api/document.api";
import { waitForDocumentProcessed } from "../../documents/api/document-status.poller";
import { isDocumentProcessed } from "../../documents/lib/document-status";
import { runDocumentUpload } from "../../transfers/document-transfer-flows.js";

export function useDocumentQuestionFlow({ documentClient, conversationId, clearSelectedFile, transfers }) {
  async function uploadAndWait(file) {
    const document = await runDocumentUpload({
      transfers, file, conversationId,
      upload: () => uploadDocument(documentClient, { file, conversationId }),
      poll: (id) => waitForDocumentProcessed(documentClient, id), isProcessed: isDocumentProcessed,
    });
    clearSelectedFile();
    return document;
  }
  return { uploadAndWait };
}
