import { env } from "@/app/config/env.ts";
import { createSessionClient } from "@/shared/api/session-client.ts";
import type { SessionSnapshot } from "@/shared/api/session-client.ts";

export function createSessionClients(
  key: string | null,
  read: () => SessionSnapshot,
) {
  const client = (url: string) =>
    key ? createSessionClient(url, key, read) : null;
  return {
    chatClient: client(env.ragChatBaseUrl),
    documentClient: client(env.ragDocumentBaseUrl),
    documentSearchClient: client(env.documentSearchBaseUrl),
    documentAccessClient: client(env.documentAccessBaseUrl),
    documentLibraryClient: client(env.documentLibraryBaseUrl),
    documentTransferClient: client(env.documentTransferBaseUrl),
    documentExportClient: client(env.documentExportBaseUrl),
    googleDriveImportClient: client(env.googleDriveImportBaseUrl),
    conversationClient: client(env.conversationBaseUrl),
    authClient: client(env.authBaseUrl),
    profileClient: client(env.profileBaseUrl),
  };
}
