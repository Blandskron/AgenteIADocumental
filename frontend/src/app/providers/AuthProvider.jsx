import { createContext, useContext, useMemo, useRef } from "react";

import { env } from "../config/env";
import { createAuthorizedClient } from "../../shared/api/httpClient";
import { useAuth } from "../../features/auth/hooks/useAuth";
import { createProfileSessionClient } from "../../features/profile/api/session-client.js";
import { useProfile } from "../../features/profile/hooks/useProfile.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const authState = useAuth();
  const profileSessionKey = authState.auth?.access
    ? JSON.stringify([authState.auth.sessionId, authState.currentUser?.id, authState.currentUser?.activeTenantId]) : null;
  const session = useRef(null);
  session.current = { ...authState, key: profileSessionKey };

  const chatClient = useMemo(
    () =>
      createAuthorizedClient({
        baseUrl: env.ragChatBaseUrl,
        getAccessToken: () => authState.auth?.access,
        refreshAccessToken: authState.refreshAccessToken,
        onUnauthorized: authState.logout,
      }),
    [authState.auth?.access, authState.logout, authState.refreshAccessToken],
  );

  const documentClient = useMemo(
    () =>
      createAuthorizedClient({
        baseUrl: env.ragDocumentBaseUrl,
        getAccessToken: () => authState.auth?.access,
        refreshAccessToken: authState.refreshAccessToken,
        onUnauthorized: authState.logout,
      }),
    [authState.auth?.access, authState.logout, authState.refreshAccessToken],
  );

  const documentSearchClient = useMemo(
    () =>
      createAuthorizedClient({
        baseUrl: env.documentSearchBaseUrl,
        getAccessToken: () => authState.auth?.access,
        refreshAccessToken: authState.refreshAccessToken,
        onUnauthorized: authState.logout,
      }),
    [authState.auth?.access, authState.logout, authState.refreshAccessToken],
  );

  const documentAccessClient = useMemo(
    () =>
      createAuthorizedClient({
        baseUrl: env.documentAccessBaseUrl,
        getAccessToken: () => authState.auth?.access,
        refreshAccessToken: authState.refreshAccessToken,
        onUnauthorized: authState.logout,
      }),
    [authState.auth?.access, authState.logout, authState.refreshAccessToken],
  );

  const documentLibraryClient = useMemo(
    () =>
      createAuthorizedClient({
        baseUrl: env.documentLibraryBaseUrl,
        getAccessToken: () => authState.auth?.access,
        refreshAccessToken: authState.refreshAccessToken,
        onUnauthorized: authState.logout,
      }),
    [authState.auth?.access, authState.logout, authState.refreshAccessToken],
  );

  const documentTransferClient = useMemo(
    () =>
      createAuthorizedClient({
        baseUrl: env.documentTransferBaseUrl,
        getAccessToken: () => authState.auth?.access,
        refreshAccessToken: authState.refreshAccessToken,
        onUnauthorized: authState.logout,
      }),
    [authState.auth?.access, authState.logout, authState.refreshAccessToken],
  );

  const documentExportClient = useMemo(
    () =>
      createAuthorizedClient({
        baseUrl: env.documentExportBaseUrl,
        getAccessToken: () => authState.auth?.access,
        refreshAccessToken: authState.refreshAccessToken,
        onUnauthorized: authState.logout,
      }),
    [authState.auth?.access, authState.logout, authState.refreshAccessToken],
  );

  const googleDriveImportClient = useMemo(
    () =>
      createAuthorizedClient({
        baseUrl: env.googleDriveImportBaseUrl,
        getAccessToken: () => authState.auth?.access,
        refreshAccessToken: authState.refreshAccessToken,
        onUnauthorized: authState.logout,
      }),
    [authState.auth?.access, authState.logout, authState.refreshAccessToken],
  );

  const conversationClient = useMemo(
    () =>
      createAuthorizedClient({
        baseUrl: env.conversationBaseUrl,
        getAccessToken: () => authState.auth?.access,
        refreshAccessToken: authState.refreshAccessToken,
        onUnauthorized: authState.logout,
      }),
    [authState.auth?.access, authState.logout, authState.refreshAccessToken],
  );

  const authClient = useMemo(() => profileSessionKey
    ? createProfileSessionClient(env.authBaseUrl, profileSessionKey, () => session.current) : null, [profileSessionKey]);

  const profileClient = useMemo(() => profileSessionKey
    ? createProfileSessionClient(env.profileBaseUrl, profileSessionKey, () => session.current) : null, [profileSessionKey]);
  const { profile, acceptProfile: setProfile, isLoading: isProfileLoading } = useProfile(profileClient);

  const value = useMemo(
    () => ({
      ...authState,
      chatClient,
      documentClient,
      documentSearchClient,
      documentAccessClient,
      documentLibraryClient,
      documentTransferClient,
      documentExportClient,
      googleDriveImportClient,
      conversationClient,
      authClient,
      profileClient,
      profileSessionKey,
      profile,
      setProfile,
      isProfileLoading,
    }),
    [
      authState,
      chatClient,
      documentClient,
      documentSearchClient,
      documentAccessClient,
      documentLibraryClient,
      documentTransferClient,
      documentExportClient,
      googleDriveImportClient,
      conversationClient,
      authClient,
      profileClient,
      profileSessionKey,
      profile,
      setProfile,
      isProfileLoading,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuthContext() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuthContext must be used inside AuthProvider");
  }

  return context;
}
