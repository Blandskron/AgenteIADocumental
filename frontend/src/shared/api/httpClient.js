export class ApiError extends Error {
  constructor(message, { status = 0, payload = null } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

function getErrorMessage(payload, status) {
  if (typeof payload === "string") return payload;
  if (Array.isArray(payload?.detail)) {
    return payload.detail.map((error) => {
      const field = (error.loc || []).filter((part) => !["body", "query", "path"].includes(part)).join(".");
      return `${field ? `${field}: ` : ""}${error.msg || "Valor no válido"}`;
    }).join("; ");
  }
  if (typeof payload?.detail === "string") return payload.detail;
  if (payload?.error) return payload.error;
  if (payload?.message) return payload.message;
  if (payload && typeof payload === "object") return JSON.stringify(payload);
  return `HTTP ${status}`;
}

function networkError(baseUrl) {
  return new ApiError(`No se pudo conectar con el microservicio ${baseUrl}. Verifica que este disponible.`, {
    status: 0,
  });
}

async function safeFetch(baseUrl, path, options) {
  try {
    return await fetch(`${baseUrl}${path}`, options);
  } catch (error) {
    if (error instanceof TypeError) {
      throw networkError(baseUrl);
    }
    throw error;
  }
}

export async function parseResponse(response) {
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();

  if (!response.ok) {
    throw new ApiError(getErrorMessage(payload, response.status), {
      status: response.status,
      payload,
    });
  }

  return payload;
}

async function parseBlobResponse(response) {
  const payload = await response.blob();

  if (!response.ok) {
    throw new ApiError(`HTTP ${response.status}`, {
      status: response.status,
      payload,
    });
  }

  return {
    blob: payload,
    contentType: response.headers.get("content-type") || "",
    contentDisposition: response.headers.get("content-disposition") || "",
  };
}

export async function httpRequest(baseUrl, path, options = {}) {
  const response = await safeFetch(baseUrl, path, options);
  return parseResponse(response);
}

export function createAuthorizedClient({ baseUrl, getAccessToken, refreshAccessToken, onUnauthorized }) {
  return async function authorizedRequest(path, options = {}) {
    const { responseType, ...fetchOptions } = options;
    const headers = new Headers(options.headers || {});
    const accessToken = getAccessToken();

    if (accessToken) {
      headers.set("Authorization", `Bearer ${accessToken}`);
    }

    const response = await safeFetch(baseUrl, path, { ...fetchOptions, headers });

    if (response.status === 401) {
      let newAccessToken = null;

      try {
        newAccessToken = await refreshAccessToken?.();
      } catch {
        onUnauthorized?.();
      }

      if (newAccessToken) {
        const retryHeaders = new Headers(options.headers || {});
        retryHeaders.set("Authorization", `Bearer ${newAccessToken}`);
        const retryResponse = await safeFetch(baseUrl, path, { ...fetchOptions, headers: retryHeaders });

        if (retryResponse.status !== 401) {
          return responseType === "blob" ? parseBlobResponse(retryResponse) : parseResponse(retryResponse);
        }

        throw new ApiError("No tienes permisos para consultar este modulo.", {
          status: 401,
        });
      }

      throw new ApiError("Sesion expirada. Inicia sesion nuevamente.", {
        status: 401,
      });
    }

    return responseType === "blob" ? parseBlobResponse(response) : parseResponse(response);
  };
}
