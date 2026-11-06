import { uploadDocument } from "../../documents/api/document.api";
import { waitForDocumentProcessed } from "../../documents/api/document-status.poller";
import { isDocumentProcessed } from "../../documents/lib/document-status";
import { transferFailureUpdate } from "../../transfers/lib/failure-update";

export function useDocumentQuestionFlow({ documentClient, conversationId, clearSelectedFile, transfers }) {
  async function uploadAndWait(file) {
    let transfer = null;

    try {
      transfer = await transfers?.recordTransfer({
        filename: file.name,
        direction: "UPLOAD",
        status: "RUNNING",
        progress: 15,
        size_bytes: file.size,
        metadata: { conversation_id: conversationId },
      });

      const document = await uploadDocument(documentClient, {
        file,
        conversationId,
      });

      await transfers?.patchTransfer(transfer?.transferId, {
        document_id: document.documentId,
        progress: isDocumentProcessed(document.status) ? 100 : 65,
        status: isDocumentProcessed(document.status) ? "COMPLETED" : "RUNNING",
      });

      if (!isDocumentProcessed(document.status)) {
        const processedDocument = await waitForDocumentProcessed(documentClient, document.documentId);
        await transfers?.patchTransfer(transfer?.transferId, {
          document_id: document.documentId,
          progress: 100,
          status: "COMPLETED",
        });
        clearSelectedFile();
        return processedDocument;
      }

      clearSelectedFile();
      return document;
    } catch (error) {
      await transfers?.patchTransfer(transfer?.transferId, transferFailureUpdate(error, { conversation_id: conversationId }));
      throw error;
    }
  }

  return {
    uploadAndWait,
  };
}
