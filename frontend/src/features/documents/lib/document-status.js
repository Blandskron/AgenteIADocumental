export const DOCUMENT_STATUS = {
  pending: "PENDING",
  processing: "PROCESSING",
  processed: "PROCESSED",
  failed: "FAILED",
  reindexRequired: "REINDEX_REQUIRED",
};

export function isDocumentProcessed(status) {
  return status === DOCUMENT_STATUS.processed;
}

export function isDocumentFailed(status) {
  return status === DOCUMENT_STATUS.failed;
}
