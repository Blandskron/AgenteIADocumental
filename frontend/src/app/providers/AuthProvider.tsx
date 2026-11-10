import type { Profile } from "@/features/profile/model/types.ts";
import type { PropsWithChildren } from "react";
import { createContext, useCallback, useContext, useMemo, useRef } from "react";

import { createSessionClients } from "./session-clients.ts";
import { useAuth } from "@/features/auth/hooks/useAuth.ts";
import { useProfile } from "@/features/profile/hooks/useProfile.ts";

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: PropsWithChildren) {
  const authState = useAuth();
  const profileSessionKey = authState.auth?.access
    ? JSON.stringify([
        authState.auth.sessionId,
        authState.currentUser?.id,
        authState.currentUser?.activeTenantId,
      ])
    : null;
  const session = useRef({ ...authState, key: profileSessionKey });
  session.current = { ...authState, key: profileSessionKey };
  const readSession = useCallback(() => {
    const state = session.current;
    const auth = state.readAuthSession();
    const user = auth?.user;
    const key =
      auth?.access && user
        ? JSON.stringify([auth.sessionId, user.id, user.activeTenantId])
        : null;
    return { ...state, auth, key };
  }, []);

  const clients = useMemo(
    () => createSessionClients(profileSessionKey, readSession),
    [profileSessionKey, readSession],
  );
  const {
    profile,
    acceptProfile: setProfile,
    isLoading: isProfileLoading,
  } = useProfile(clients.profileClient);

  const value = useMemo(
    () => ({
      ...authState,
      ...clients,
      profileSessionKey,
      profile,
      setProfile,
      isProfileLoading,
    }),
    [
      authState,
      clients,
      profileSessionKey,
      profile,
      setProfile,
      isProfileLoading,
    ],
  );

  // A different account/tenant must not persist the previous page's local state.
  return (
    <AuthContext.Provider key={profileSessionKey || "signed-out"} value={value}>
      {children}
    </AuthContext.Provider>
  );
}

type AuthContextValue = ReturnType<typeof useAuth> &
  ReturnType<typeof createSessionClients> & {
    profileSessionKey: string | null;
    profile: Profile | null;
    setProfile: (profile: Profile) => void;
    isProfileLoading: boolean;
  };

export function useAuthContext() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuthContext must be used inside AuthProvider");
  }

  return context;
}
