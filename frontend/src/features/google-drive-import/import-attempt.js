const storageKey = (scope) => `blandskron.drive.import.${scope}`;

export function prepareImportAttempt(scope, input, connectionVersion, storage = sessionStorage, uuid = () => crypto.randomUUID()) {
  if (!scope) throw new Error("Inicia sesión para importar documentos.");
  const signature = JSON.stringify(input);
  let previous;
  try { previous = JSON.parse(storage.getItem(storageKey(scope))); } catch { throw new Error("Revisa la operación anterior antes de crear otra importación."); }
  if (previous?.signature === signature && !["FAILED", "REJECTED"].includes(previous.outcome)) return previous;
  if (previous && !previous.finished) throw new Error("Hay una importación sin resultado confirmado. Reintenta la selección anterior y revisa su resultado antes de cambiarla.");
  const attempt = { signature, operationId: uuid(), connectionVersion, finished: false };
  storage.setItem(storageKey(scope), JSON.stringify(attempt));
  return attempt;
}

export function finishImportAttempt(scope, operationId, result, storage = sessionStorage) {
  const key = storageKey(scope), previous = JSON.parse(storage.getItem(key));
  if (previous?.operationId !== operationId) return;
  // Keep the original key for the same selection; the server also fences unresolved source files.
  storage.setItem(key, JSON.stringify({ ...previous, finished: true, outcome: result.status }));
}

export function rejectImportAttempt(scope, operationId, error, storage = sessionStorage) {
  if ([400, 404, 413, 422].includes(error.status) || ["import_source_conflict", "import_connection_changed"].includes(error.payload?.code)) {
    finishImportAttempt(scope, operationId, { status: "REJECTED" }, storage);
  }
}

export function pendingImportAttempt(scope, storage = sessionStorage) {
  try {
    const previous = JSON.parse(storage.getItem(storageKey(scope)));
    return previous && !previous.finished ? JSON.parse(previous.signature) : null;
  } catch { return null; }
}
