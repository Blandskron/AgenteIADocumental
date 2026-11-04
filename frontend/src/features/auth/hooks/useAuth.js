import { useEffect, useState, useCallback, useMemo } from "react";

import { normalizeAuthUser, userFromAccessToken, userStorageScope } from "../../../entities/auth/model/auth.user";
import { loadAuthSession, saveAuthSession, clearAuthSession } from "../../../entities/auth/model/auth.storage";
import { loginRequest, meRequest, refreshTokenRequest } from "../api/auth.api";

export function useAuth() {
  const [auth, setAuth] = useState(loadAuthSession);
  const [loginError, setLoginError] = useState("");
  const [isAuthenticating, setIsAuthenticating] = useState(false);

  useEffect(() => {
    if (auth) {
      saveAuthSession(auth);
    } else {
      clearAuthSession();
    }
  }, [auth]);

  useEffect(() => {
    if (!auth?.access) return;
    meRequest(auth.access)
      .then((user) => {
        setAuth((current) => (current?.access === auth.access ? { ...current, user: normalizeAuthUser(user) } : current));
      })
      .catch(() => {});
  }, [auth?.access]);

  const login = useCallback(async (credentials) => {
    setIsAuthenticating(true);
    setLoginError("");

    try {
      const payload = await loginRequest(credentials);
      const user = normalizeAuthUser(payload, credentials.username);
      setAuth({
        access: payload.access,
        refresh: payload.refresh,
        username: user.username,
        user,
      });
      return true;
    } catch (error) {
      setLoginError(error.message);
      return false;
    } finally {
      setIsAuthenticating(false);
    }
  }, []);

  const refreshAccessToken = useCallback(async () => {
    if (!auth?.refresh) return null;

    try {
      const payload = await refreshTokenRequest(auth.refresh);
      const nextAuth = {
        ...auth,
        access: payload.access,
        refresh: payload.refresh || auth.refresh,
        user: payload.user ? normalizeAuthUser(payload.user) : userFromAccessToken(payload.access, auth.username),
      };
      setAuth(nextAuth);
      return nextAuth.access;
    } catch {
      setAuth(null);
      return null;
    }
  }, [auth]);

  const logout = useCallback(() => {
    setAuth(null);
  }, []);

  const currentUser = useMemo(() => {
    return auth?.user || userFromAccessToken(auth?.access, auth?.username);
  }, [auth]);

  const storageScope = useMemo(() => {
    return userStorageScope(currentUser);
  }, [currentUser]);

  return useMemo(
    () => ({
      auth,
      currentUser,
      storageScope,
      isAuthenticated: Boolean(auth?.access),
      isAuthenticating,
      loginError,
      login,
      refreshAccessToken,
      logout,
    }),
    [
      auth,
      currentUser,
      storageScope,
      isAuthenticating,
      loginError,
      login,
      refreshAccessToken,
      logout,
    ]
  );
}

