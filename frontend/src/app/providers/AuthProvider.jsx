import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { env } from "../config/env";
import { createAuthorizedClient } from "../../shared/api/httpClient";
import { useAuth } from "../../features/auth/hooks/useAuth";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const authState = useAuth();

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

  const authClient = useMemo(
    () =>
      createAuthorizedClient({
        baseUrl: env.authBaseUrl,
        getAccessToken: () => authState.auth?.access,
        refreshAccessToken: authState.refreshAccessToken,
        onUnauthorized: authState.logout,
      }),
    [authState.auth?.access, authState.logout, authState.refreshAccessToken],
  );

  const profileClient = useMemo(
    () =>
      createAuthorizedClient({
        baseUrl: env.profileBaseUrl,
        getAccessToken: () => authState.auth?.access,
        refreshAccessToken: authState.refreshAccessToken,
        onUnauthorized: authState.logout,
      }),
    [authState.auth?.access, authState.logout, authState.refreshAccessToken],
  );

  const [profile, setProfile] = useState(null);
  const [isProfileLoading, setIsProfileLoading] = useState(false);

  useEffect(() => {
    if (!authState.auth?.access) {
      setProfile(null);
      return;
    }

    let isMounted = true;
    setIsProfileLoading(true);

    profileClient("/api/v1/profile", { method: "GET" })
      .then((data) => {
        if (isMounted) {
          setProfile(data);
          setIsProfileLoading(false);
        }
      })
      .catch(() => {
        if (isMounted) {
          setIsProfileLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [authState.auth?.access, profileClient]);

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
      profile,
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
