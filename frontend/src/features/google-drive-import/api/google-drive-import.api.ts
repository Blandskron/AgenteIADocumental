import type { MaybeClient } from "@/shared/api/types.ts";
import { requireClient } from "@/shared/api/types.ts";
import type { DriveInput } from "../types.ts";
interface ConnectionDto {
  connected?: boolean;
  enabled?: boolean;
  version?: number;
  grant_status?: string;
  busy?: boolean;
  provider_account_id?: string;
  oauth_client_id?: string;
  picker_app_id?: string;
  provider_account_email?: string;
  scopes?: string[];
  expires_at?: string;
}
interface ImportDto {
  import_id?: string;
  operation_id?: string;
  version?: number;
  owner_user_id?: string;
  status?: string;
  total_files?: number;
  processed_files?: number;
  failed_files?: number;
  metadata?: Record<string, unknown>;
  error_message?: string;
  created_at?: string;
  updated_at?: string;
  files?: ImportFileDto[];
}
interface ImportFileDto {
  import_file_id?: string;
  import_id?: string;
  google_file_id?: string;
  filename?: string;
  mime_type?: string;
  export_mime_type?: string;
  size_bytes?: number;
  status?: string;
  document_id?: string;
  metadata?: Record<string, unknown>;
  error_message?: string;
  created_at?: string;
  updated_at?: string;
}
function normalizeConnection(payload: ConnectionDto = {}) {
  return {
    connected: Boolean(payload.connected),
    enabled: Boolean(payload.enabled),
    version: payload.version,
    grantStatus: payload.grant_status,
    busy: Boolean(payload.busy),
    providerAccountId: payload.provider_account_id,
    oauthClientId: payload.oauth_client_id,
    pickerAppId: payload.picker_app_id,
    providerAccountEmail: payload.provider_account_email,
    scopes: payload.scopes || [],
    expiresAt: payload.expires_at,
  };
}

function normalizeImport(payload: ImportDto = {}) {
  return {
    importId: payload.import_id || "",
    operationId: payload.operation_id,
    version: payload.version,
    ownerUserId: payload.owner_user_id,
    status: payload.status || "UNKNOWN",
    totalFiles: payload.total_files,
    processedFiles: payload.processed_files,
    failedFiles: payload.failed_files,
    metadata: payload.metadata || {},
    errorMessage: payload.error_message,
    createdAt: payload.created_at,
    updatedAt: payload.updated_at,
    files: Array.isArray(payload.files)
      ? payload.files.map(normalizeImportFile)
      : [],
  };
}

function normalizeImportFile(payload: ImportFileDto = {}) {
  return {
    importFileId: payload.import_file_id || "",
    importId: payload.import_id || "",
    googleFileId: payload.google_file_id,
    filename: payload.filename,
    mimeType: payload.mime_type,
    exportMimeType: payload.export_mime_type,
    sizeBytes: payload.size_bytes,
    status: payload.status || "UNKNOWN",
    documentId: payload.document_id || "",
    metadata: payload.metadata || {},
    errorMessage: payload.error_message,
    createdAt: payload.created_at,
    updatedAt: payload.updated_at,
  };
}

export function getGoogleDriveAuthUrl(
  apiClient: MaybeClient,
  codeChallenge: string,
) {
  return requireClient(apiClient)<{
    authorization_url: string;
    redirect_uri: string;
    state: string;
  }>("/api/v1/google-drive/auth-url", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code_challenge: codeChallenge }),
  });
}

export function connectGoogleDrive(
  apiClient: MaybeClient,
  payload: {
    code: string;
    state: string;
    code_verifier: string;
    issuer?: string;
  },
) {
  return requireClient(apiClient)<Parameters<typeof normalizeConnection>[0]>(
    "/api/v1/google-drive/oauth/callback",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  ).then(normalizeConnection);
}

export function disconnectGoogleDrive(
  apiClient: MaybeClient,
  version: number | undefined,
) {
  return requireClient(apiClient)<Parameters<typeof normalizeConnection>[0]>(
    "/api/v1/google-drive/disconnect",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ version }),
    },
  ).then(normalizeConnection);
}

export function getGoogleDriveConnection(apiClient: MaybeClient) {
  return requireClient(apiClient)<Parameters<typeof normalizeConnection>[0]>(
    "/api/v1/google-drive/connection",
    { method: "GET" },
  ).then(normalizeConnection);
}

export function importGoogleDriveFiles(
  apiClient: MaybeClient,
  {
    files,
    folderId = null,
    metadata = {},
    operationId,
    connectionVersion,
    signal,
  }: DriveInput & {
    operationId: string;
    connectionVersion?: number;
    signal?: AbortSignal;
  },
) {
  if (!operationId)
    throw new Error("La importación requiere una clave de operación.");
  return requireClient(apiClient)<Parameters<typeof normalizeImport>[0]>(
    "/api/v1/google-drive/imports",
    {
      method: "POST",
      signal,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        operation_id: operationId,
        connection_version: connectionVersion,
        files: files.map((file) => ({
          file_id: file.fileId || file.id,
          name: file.name,
          mime_type: file.mimeType,
          export_mime_type: file.exportMimeType,
        })),
        folder_id: folderId,
        metadata,
      }),
    },
  ).then(normalizeImport);
}

function page<T, R>(
  payload: { items: T[]; next_cursor: string | null },
  normalize: (item: T) => R,
  id: keyof T,
) {
  if (
    !payload ||
    !Array.isArray(payload.items) ||
    payload.items.length > 100 ||
    !(
      payload.next_cursor === null ||
      (typeof payload.next_cursor === "string" &&
        /^[A-Za-z0-9_-]{1,1024}$/.test(payload.next_cursor))
    ) ||
    payload.items.some(
      (item) => !item || typeof item[id] !== "string" || !item[id],
    ) ||
    new Set(payload.items.map((item) => item[id])).size !==
      payload.items.length ||
    (payload.next_cursor && !payload.items.length)
  )
    throw new Error("Respuesta de historial de Drive inválida.");
  return {
    items: payload.items.map(normalize),
    nextCursor: payload.next_cursor,
  };
}
export function listGoogleDriveImports(
  apiClient: MaybeClient,
  {
    limit = 25,
    cursor,
    signal,
  }: { limit?: number; cursor?: string | null; signal?: AbortSignal } = {},
) {
  const query = new URLSearchParams({ limit: String(limit) });
  if (cursor) query.set("before", cursor);
  return requireClient(apiClient)<{
    items: ImportDto[];
    next_cursor: string | null;
  }>(`/api/v1/google-drive/imports?${query}`, { method: "GET", signal }).then(
    (payload) => page(payload, normalizeImport, "import_id"),
  );
}
export function getGoogleDriveImport(
  apiClient: MaybeClient,
  importId: string,
  signal: AbortSignal | undefined,
) {
  return requireClient(apiClient)<Parameters<typeof normalizeImport>[0]>(
    `/api/v1/google-drive/imports/${encodeURIComponent(importId)}`,
    { method: "GET", signal },
  ).then(normalizeImport);
}
export function listGoogleDriveImportFiles(
  apiClient: MaybeClient,
  importId: string,
  {
    limit = 25,
    cursor,
    signal,
  }: { limit?: number; cursor?: string | null; signal?: AbortSignal } = {},
) {
  const query = new URLSearchParams({ limit: String(limit) });
  if (cursor) query.set("after", cursor);
  return requireClient(apiClient)<{
    items: ImportFileDto[];
    next_cursor: string | null;
  }>(
    `/api/v1/google-drive/imports/${encodeURIComponent(importId)}/files?${query}`,
    { method: "GET", signal },
  ).then((payload) => page(payload, normalizeImportFile, "import_file_id"));
}
