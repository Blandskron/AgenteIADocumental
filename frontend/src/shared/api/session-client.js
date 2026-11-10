import { createAuthorizedClient } from "./httpClient.js";

// A refresh changes credentials, not the session owning an editor or request.
export function createSessionClient(baseUrl, sessionKey, readSession) {
  const current = () => sessionKey && readSession().key === sessionKey;
  const assertCurrent = () => {
    if (!current()) throw new DOMException("La sesión cambió.", "AbortError");
  };
  let refreshPending = null;
  const request = createAuthorizedClient({
    baseUrl,
    getAccessToken: () => { assertCurrent(); return readSession().auth.access; },
    refreshAccessToken: async (rejectedAccess) => {
      assertCurrent();
      if (!refreshPending) {
        refreshPending = Promise.resolve().then(() => {
          assertCurrent();
          return readSession().refreshAccessToken(rejectedAccess);
        }).finally(() => { refreshPending = null; });
      }
      const access = await refreshPending;
      assertCurrent();
      return access;
    },
    onUnauthorized: () => { if (current()) readSession().logout(); },
  });
  return async (path, options = {}) => {
    assertCurrent();
    try {
      const result = await request(path, options);
      assertCurrent();
      return result;
    } catch (error) {
      assertCurrent();
      if (error.status === 401) readSession().logout();
      throw error;
    }
  };
}
