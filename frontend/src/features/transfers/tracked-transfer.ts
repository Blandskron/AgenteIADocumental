import { toError } from "@/shared/lib/errors.ts";
import type { Transfer, TransferInput } from "./api/transfers.api.ts";
import { transferFailureUpdate } from "./lib/failure-update.ts";
export interface TransferJournal {
  captureJournal: () => {
    isActive: () => boolean;
    recordTransfer: (input: TransferInput) => Promise<Transfer | null>;
    patchTransfer: (
      id: string,
      patch: Partial<TransferInput>,
    ) => Promise<Transfer | null>;
    noteWarning: (error: { message?: string }) => void;
  };
}

// Journal work is ordered per operation, but never blocks or repeats the file operation.
export async function runDocumentTransfer<T>({
  transfers,
  initial,
  operation,
}: {
  transfers?: TransferJournal;
  initial: TransferInput;
  operation: (report: (patch: Partial<TransferInput>) => void) => Promise<T>;
}) {
  const journal = transfers?.captureJournal?.();
  if (journal && !journal.isActive())
    throw new Error("La sesión cambió. Inicia de nuevo la operación.");
  async function attempt(
    callback: () => Promise<Transfer | null>,
    fallback: Transfer | null,
  ) {
    if (!journal?.isActive()) return fallback;
    try {
      return await callback();
    } catch (caughtError) {
      const error = toError(caughtError);
      journal.noteWarning(error);
      return fallback;
    }
  }
  let queue = Promise.resolve().then(() =>
    attempt(() => journal!.recordTransfer(initial), null),
  );
  const report = (payload: Partial<TransferInput>) => {
    queue = queue.then((row) =>
      row?.transferId
        ? attempt(() => journal!.patchTransfer(row.transferId, payload), row)
        : row,
    );
  };
  try {
    const result = await operation(report);
    report({
      status: "COMPLETED",
      progress: 100,
      ...(typeof result === "object" &&
      result !== null &&
      "documentId" in result &&
      typeof result.documentId === "string"
        ? { document_id: result.documentId }
        : {}),
    });
    return result;
  } catch (caughtError) {
    const error = toError(caughtError);
    report(transferFailureUpdate(error, initial.metadata));
    throw caughtError;
  }
}
