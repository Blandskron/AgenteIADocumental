import { errorStatus } from "@/shared/lib/errors.ts";
import { createAuthorizedClient } from "./httpClient.ts";
import type { ApiClient, BlobResponse, RequestOptions } from "./types.ts";
export interface SessionSnapshot {
  key: string | null;
  auth: { access: string } | null;
  refreshAccessToken: (
    rejectedAccess?: string | null,
  ) => Promise<string | null>;
  logout: () => void;
}
// A refresh changes credentials, not the session owning an editor or request.
export function createSessionClient(
  baseUrl: string,
  sessionKey: string,
  readSession: () => SessionSnapshot,
): ApiClient {
  const current = () => readSession().key === sessionKey;
  const assertCurrent = () => {
    if (!current()) throw new DOMException("La sesión cambió.", "AbortError");
  };
  let refreshPending: Promise<string | null> | null = null;
  const request = createAuthorizedClient({
    baseUrl,
    getAccessToken: () => {
      assertCurrent();
      return readSession().auth?.access;
    },
    refreshAccessToken: async (rejectedAccess) => {
      assertCurrent();
      refreshPending ??= Promise.resolve()
        .then(() => {
          assertCurrent();
          return readSession().refreshAccessToken(rejectedAccess);
        })
        .finally(() => {
          refreshPending = null;
        });
      const access = await refreshPending;
      assertCurrent();
      return access;
    },
    onUnauthorized: () => {
      if (current()) readSession().logout();
    },
  });
  async function scopedRequest<T = unknown>(
    path: string,
    options: RequestOptions = {},
  ): Promise<T | BlobResponse> {
    assertCurrent();
    try {
      const result =
        options.responseType === "blob"
          ? await request(path, { ...options, responseType: "blob" })
          : await request<T>(path, {
              ...options,
              responseType: options.responseType,
            });
      assertCurrent();
      return result;
    } catch (error) {
      assertCurrent();
      if (errorStatus(error) === 401) readSession().logout();
      throw error;
    }
  }
  return scopedRequest as ApiClient;
}
