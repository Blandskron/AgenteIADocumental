export function errorMessage(
  error: unknown,
  fallback = "No se pudo completar la operación.",
): string {
  return error instanceof Error ? error.message : fallback;
}

export function errorStatus(error: unknown): number {
  return typeof error === "object" &&
    error !== null &&
    "status" in error &&
    typeof error.status === "number"
    ? error.status
    : 0;
}

export function toError(error: unknown) {
  const payload =
    typeof error === "object" && error !== null && "payload" in error
      ? error.payload
      : null;
  const code =
    typeof payload === "object" &&
    payload !== null &&
    "code" in payload &&
    typeof payload.code === "string"
      ? payload.code
      : "";
  return {
    message: errorMessage(error),
    status: errorStatus(error),
    name: error instanceof Error ? error.name : "Error",
    payload: { code },
  };
}
