// Omit progress: the server retains the last accepted stage, including concurrent advances.
// An existing personal journal can record failure after document access was revoked.
export function transferFailureUpdate(
  error: { name?: string; message?: string },
  metadata: Record<string, unknown> = {},
) {
  return {
    status: "FAILED",
    metadata: {
      ...metadata,
      error: error?.message || String(error ?? "Error desconocido"),
    },
  };
}
