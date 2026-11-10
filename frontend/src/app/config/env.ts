const runtimeConfig = window.__BLANDSKRON_CONFIG__ || {};

function readEnv(key: string, fallback: string) {
  return runtimeConfig[key] || import.meta.env[key] || fallback;
}

function trimTrailingSlash(value: string) {
  return value.replace(/\/+$/, "");
}

function requiredUrl(key: string, fallback: string) {
  const value = readEnv(key, fallback);

  if (!value) {
    throw new Error(`Missing required frontend environment variable: ${key}`);
  }

  return trimTrailingSlash(value);
}

export const env = {
  googleClientId: readEnv("VITE_GOOGLE_CLIENT_ID", ""),
  googlePickerApiKey: readEnv("VITE_GOOGLE_PICKER_API_KEY", ""),
  googlePickerAppId:
    readEnv("VITE_GOOGLE_PICKER_APP_ID", "") ||
    readEnv("VITE_GOOGLE_CLIENT_ID", "").split("-")[0],
  authBaseUrl: requiredUrl("VITE_AUTH_BASE_URL", "http://localhost:8001"),
  ragChatBaseUrl: requiredUrl(
    "VITE_RAG_CHAT_BASE_URL",
    "http://localhost:8002",
  ),
  ragDocumentBaseUrl: requiredUrl(
    "VITE_RAG_DOCUMENT_BASE_URL",
    "http://localhost:8003",
  ),
  documentSearchBaseUrl: requiredUrl(
    "VITE_DOCUMENT_SEARCH_BASE_URL",
    "http://localhost:8004",
  ),
  documentAccessBaseUrl: requiredUrl(
    "VITE_DOCUMENT_ACCESS_BASE_URL",
    "http://localhost:8005",
  ),
  documentLibraryBaseUrl: requiredUrl(
    "VITE_DOCUMENT_LIBRARY_BASE_URL",
    "http://localhost:8006",
  ),
  documentTransferBaseUrl: requiredUrl(
    "VITE_DOCUMENT_TRANSFER_BASE_URL",
    "http://localhost:8007",
  ),
  documentExportBaseUrl: requiredUrl(
    "VITE_DOCUMENT_EXPORT_BASE_URL",
    "http://localhost:8016",
  ),
  googleDriveImportBaseUrl: requiredUrl(
    "VITE_GOOGLE_DRIVE_IMPORT_BASE_URL",
    "http://localhost:8017",
  ),
  conversationBaseUrl: requiredUrl(
    "VITE_CONVERSATION_BASE_URL",
    "http://localhost:8008",
  ),
  profileBaseUrl: requiredUrl("VITE_PROFILE_BASE_URL", "http://localhost:8015"),
};
