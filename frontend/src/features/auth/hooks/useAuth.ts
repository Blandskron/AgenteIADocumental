import type { Credentials } from "@/entities/auth/model/types.ts";
import { toError } from "@/shared/lib/errors.ts";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  clearAuthSession,
  loadAuthSession,
  saveAuthSession,
} from "@/entities/auth/model/auth.storage";
import {
  normalizeAuthUser,
  userFromAccessToken,
  userStorageScope,
} from "@/entities/auth/model/auth.user";
import {
  loginRequest,
  logoutRequest,
  meRequest,
  refreshTokenRequest,
} from "@/features/auth/api/auth.api";

export function useAuth() {
  const [auth, setAuth] = useState(() => {
    const saved = loadAuthSession();
    if (!saved?.access) return null;
    const sessionId =
      typeof saved.sessionId === "string" &&
      /^[a-f0-9-]{36}$/.test(saved.sessionId)
        ? saved.sessionId
        : crypto.randomUUID();
    return {
      ...saved,
      sessionId,
      user: saved.user || userFromAccessToken(saved.access, saved.username),
    };
  });
  const [loginError, setLoginError] = useState("");
  const [isAuthenticating, setIsAuthenticating] = useState(false);
  const authRef = useRef(auth);
  authRef.current = auth;
  const generation = useRef(0);
  const mounted = useRef(false);
  const refreshPending = useRef<{
    refresh: string;
    promise: Promise<string | null>;
  } | null>(null);
  const readAuthSession = useCallback(() => authRef.current, []);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    if (auth) {
      saveAuthSession(auth);
    } else {
      clearAuthSession();
    }
  }, [auth]);

  const login = useCallback(async (credentials: Credentials) => {
    const operation = ++generation.current;
    setIsAuthenticating(true);
    setLoginError("");

    try {
      const payload = await loginRequest(credentials);
      if (!mounted.current || operation !== generation.current) return false;
      const user = normalizeAuthUser(payload, credentials.username);
      const next = {
        sessionId: crypto.randomUUID(),
        access: payload.access,
        refresh: payload.refresh,
        username: user.username,
        user,
      };
      authRef.current = next;
      setAuth(next);
      return true;
    } catch (caughtError) {
      const error = toError(caughtError);
      if (!mounted.current || operation !== generation.current) return false;
      setLoginError(error.message);
      return false;
    } finally {
      if (mounted.current && operation === generation.current)
        setIsAuthenticating(false);
    }
  }, []);

  const refreshAccessToken = useCallback(
    (rejectedAccess?: string | null): Promise<string | null> => {
      const expected = authRef.current;
      if (!expected?.refresh) return Promise.resolve(null);
      if (rejectedAccess && rejectedAccess !== expected.access)
        return Promise.resolve(expected.access);
      if (refreshPending.current?.refresh === expected.refresh)
        return refreshPending.current.promise;
      const operation = generation.current;
      const promise: Promise<string | null> = Promise.resolve().then(
        async () => {
          try {
            const payload = await refreshTokenRequest(expected.refresh);
            if (
              !mounted.current ||
              operation !== generation.current ||
              authRef.current?.sessionId !== expected.sessionId
            )
              return null;
            const nextAuth = {
              ...expected,
              access: payload.access,
              refresh: payload.refresh || expected.refresh,
              user: payload.user
                ? normalizeAuthUser(payload.user)
                : userFromAccessToken(payload.access, expected.username),
            };
            authRef.current = nextAuth;
            setAuth((current) =>
              current?.refresh === expected.refresh ? nextAuth : current,
            );
            return nextAuth.access;
          } catch {
            if (
              mounted.current &&
              operation === generation.current &&
              authRef.current?.refresh === expected.refresh
            ) {
              authRef.current = null;
              setAuth((current) =>
                current?.refresh === expected.refresh ? null : current,
              );
            }
            return null;
          } finally {
            if (refreshPending.current?.promise === promise)
              refreshPending.current = null;
          }
        },
      );
      refreshPending.current = { refresh: expected.refresh, promise };
      return promise;
    },
    [],
  );

  useEffect(() => {
    if (!auth?.access) return;
    meRequest(auth.access)
      .then((user) => {
        if (!mounted.current) return;
        setAuth((current) =>
          current?.access === auth.access
            ? { ...current, user: normalizeAuthUser(user) }
            : current,
        );
      })
      .catch((error) => {
        if (error.status === 401 && authRef.current?.access === auth.access)
          refreshAccessToken(auth.access);
      });
  }, [auth?.access, refreshAccessToken]);

  const logout = useCallback(() => {
    const previous = authRef.current;
    generation.current++;
    authRef.current = null;
    setAuth(null);
    setIsAuthenticating(false);
    setLoginError("");
    if (!previous?.refresh) return;

    logoutRequest(previous.access, previous.refresh)
      .catch(async (error) => {
        if (error.status !== 401) return;
        const { access } = await refreshTokenRequest(previous.refresh);
        await logoutRequest(access, previous.refresh);
      })
      .catch(() => {});
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
      readAuthSession,
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
      readAuthSession,
    ],
  );
}
