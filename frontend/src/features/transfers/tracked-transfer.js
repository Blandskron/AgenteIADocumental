import { transferFailureUpdate } from "./lib/failure-update.js";

// Journal work is ordered per operation, but never blocks or repeats the file operation.
export async function runDocumentTransfer({ transfers, initial, operation }) {
  const journal = transfers?.captureJournal?.();
  if (journal && !journal.isActive()) throw new Error("La sesión cambió. Inicia de nuevo la operación.");
  async function attempt(callback, fallback) {
    if (!journal?.isActive()) return fallback;
    try { return await callback(); }
    catch (error) { journal.noteWarning(error); return fallback; }
  }
  let queue = Promise.resolve().then(() => attempt(() => journal.recordTransfer(initial), null));
  const report = (payload) => {
    queue = queue.then((row) => row?.transferId ? attempt(() => journal.patchTransfer(row.transferId, payload), row) : row);
  };
  try {
    const result = await operation(report);
    report({ status: "COMPLETED", progress: 100, ...(result?.documentId ? { document_id: result.documentId } : {}) });
    return result;
  } catch (error) {
    report(transferFailureUpdate(error, initial.metadata));
    throw error;
  }
}
