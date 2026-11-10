import {
  isDocumentFailed,
  isDocumentProcessed,
} from "@/features/documents/lib/document-status.ts";
import type { MaybeClient } from "@/shared/api/types.ts";
import { getDocumentStatus } from "./document.api";

const DEFAULT_INTERVAL_MS = 1500;
const DEFAULT_TIMEOUT_MS = 60000;

function delay(ms: number) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

export async function waitForDocumentProcessed(
  apiClient: MaybeClient,
  documentId: string,
  { intervalMs = DEFAULT_INTERVAL_MS, timeoutMs = DEFAULT_TIMEOUT_MS } = {},
) {
  const startedAt = Date.now();

  while (Date.now() - startedAt < timeoutMs) {
    const document = await getDocumentStatus(apiClient, documentId);

    if (isDocumentProcessed(document.status)) {
      return document;
    }

    if (isDocumentFailed(document.status)) {
      throw new Error(`El documento ${document.filename} no pudo procesarse.`);
    }

    await delay(intervalMs);
  }

  throw new Error(
    "El documento sigue procesandose. Intenta preguntar nuevamente en unos segundos.",
  );
}
