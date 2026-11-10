import type { ApiClient, BlobResponse, RequestOptions } from "./types.ts";
export class ApiError extends Error {
  readonly status: number;
  readonly payload: unknown;
  constructor(
    message: string,
    { status = 0, payload = null }: { status?: number; payload?: unknown } = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function getErrorMessage(payload: unknown, status: number): string {
  if (typeof payload === "string") return payload;
  if (isRecord(payload)) {
    if (Array.isArray(payload.detail))
      return payload.detail
        .map((error: unknown) => {
          if (!isRecord(error)) return "Valor no válido";
          const field = (Array.isArray(error.loc) ? error.loc : [])
            .filter(
              (part: unknown) =>
                !["body", "query", "path"].includes(String(part)),
            )
            .join(".");
          return `${field ? `${field}: ` : ""}${typeof error.msg === "string" ? error.msg : "Valor no válido"}`;
        })
        .join("; ");
    for (const key of ["detail", "error", "message"])
      if (typeof payload[key] === "string") return payload[key];
    return JSON.stringify(payload);
  }
  return `HTTP ${status}`;
}
async function safeFetch(
  baseUrl: string,
  path: string,
  options: RequestInit,
): Promise<Response> {
  try {
    return await fetch(baseUrl + path, options);
  } catch (error) {
    if (error instanceof TypeError)
      throw new ApiError(
        `No se pudo conectar con el microservicio ${baseUrl}. Verifica que este disponible.`,
      );
    throw error;
  }
}
// The endpoint owns its DTO; untyped callers must narrow unknown before using it.
export async function parseResponse<T = unknown>(
  response: Response,
): Promise<T> {
  const contentType = response.headers.get("content-type") || "";
  const payload: unknown =
    response.status === 204
      ? null
      : contentType.includes("application/json")
        ? await response.json()
        : await response.text();
  if (!response.ok)
    throw new ApiError(getErrorMessage(payload, response.status), {
      status: response.status,
      payload,
    });
  return payload as T;
}
async function parseBlobResponse(response: Response): Promise<BlobResponse> {
  const blob = await response.blob();
  if (!response.ok)
    throw new ApiError(`HTTP ${response.status}`, { status: response.status });
  return {
    blob,
    contentType: response.headers.get("content-type") || "",
    contentDisposition: response.headers.get("content-disposition") || "",
  };
}
export async function httpRequest<T = unknown>(
  baseUrl: string,
  path: string,
  options: RequestInit = {},
): Promise<T> {
  return parseResponse<T>(await safeFetch(baseUrl, path, options));
}
export function createAuthorizedClient({
  baseUrl,
  getAccessToken,
  refreshAccessToken,
  onUnauthorized,
}: {
  baseUrl: string;
  getAccessToken: () => string | null | undefined;
  refreshAccessToken?: (
    rejectedAccess?: string | null,
  ) => Promise<string | null>;
  onUnauthorized?: () => void;
}): ApiClient {
  async function authorizedRequest<T = unknown>(
    path: string,
    options: RequestOptions = {},
  ): Promise<T | BlobResponse> {
    const { responseType, ...fetchOptions } = options;
    const headers = new Headers(options.headers);
    const accessToken = getAccessToken();
    if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
    const response = await safeFetch(baseUrl, path, {
      ...fetchOptions,
      headers,
    });
    if (response.status === 401) {
      let newAccessToken: string | null = null;
      try {
        newAccessToken = (await refreshAccessToken?.(accessToken)) ?? null;
      } catch {
        onUnauthorized?.();
      }
      if (newAccessToken) {
        const retryHeaders = new Headers(options.headers);
        retryHeaders.set("Authorization", `Bearer ${newAccessToken}`);
        const retryResponse = await safeFetch(baseUrl, path, {
          ...fetchOptions,
          headers: retryHeaders,
        });
        if (retryResponse.status !== 401)
          return responseType === "blob"
            ? parseBlobResponse(retryResponse)
            : parseResponse<T>(retryResponse);
        throw new ApiError("No tienes permisos para consultar este modulo.", {
          status: 401,
        });
      }
      throw new ApiError("Sesion expirada. Inicia sesion nuevamente.", {
        status: 401,
      });
    }
    return responseType === "blob"
      ? parseBlobResponse(response)
      : parseResponse<T>(response);
  }
  return authorizedRequest as ApiClient;
}
