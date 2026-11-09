import { createContext, useContext, useMemo, useRef } from "react";

import { env } from "../config/env";
import { createSessionClient } from "../../shared/api/session-client.js";
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
  function readSession() {
    const state = session.current;
    const auth = state.readAuthSession();
    const user = auth?.user;
    const key = auth?.access && user ? JSON.stringify([auth.sessionId, user.id, user.activeTenantId]) : null;
    return { ...state, auth, key };
  }

  const chatClient = useMemo(() => profileSessionKey
    ? createSessionClient(env.ragChatBaseUrl, profileSessionKey, readSession) : null, [profileSessionKey]);

  const documentClient = useMemo(() => profileSessionKey
    ? createSessionClient(env.ragDocumentBaseUrl, profileSessionKey, readSession) : null, [profileSessionKey]);

  const documentSearchClient = useMemo(() => profileSessionKey
    ? createSessionClient(env.documentSearchBaseUrl, profileSessionKey, readSession) : null, [profileSessionKey]);

  const documentAccessClient = useMemo(() => profileSessionKey
    ? createSessionClient(env.documentAccessBaseUrl, profileSessionKey, readSession) : null, [profileSessionKey]);

  const documentLibraryClient = useMemo(() => profileSessionKey
    ? createSessionClient(env.documentLibraryBaseUrl, profileSessionKey, readSession) : null, [profileSessionKey]);

  const documentTransferClient = useMemo(() => profileSessionKey
    ? createSessionClient(env.documentTransferBaseUrl, profileSessionKey, readSession) : null, [profileSessionKey]);

  const documentExportClient = useMemo(() => profileSessionKey
    ? createSessionClient(env.documentExportBaseUrl, profileSessionKey, readSession) : null, [profileSessionKey]);
  const googleDriveImportClient = useMemo(() => profileSessionKey
    ? createSessionClient(env.googleDriveImportBaseUrl, profileSessionKey, readSession) : null, [profileSessionKey]);

  const conversationClient = useMemo(() => profileSessionKey
    ? createSessionClient(env.conversationBaseUrl, profileSessionKey, readSession) : null, [profileSessionKey]);

  const authClient = useMemo(() => profileSessionKey
    ? createProfileSessionClient(env.authBaseUrl, profileSessionKey, readSession) : null, [profileSessionKey]);

  const profileClient = useMemo(() => profileSessionKey
    ? createProfileSessionClient(env.profileBaseUrl, profileSessionKey, readSession) : null, [profileSessionKey]);
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
