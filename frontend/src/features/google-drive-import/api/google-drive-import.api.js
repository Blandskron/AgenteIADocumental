function normalizeConnection(payload = {}) {
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

function normalizeImport(payload = {}) {
  return {
    importId: payload.import_id,
    operationId: payload.operation_id,
    version: payload.version,
    ownerUserId: payload.owner_user_id,
    status: payload.status,
    totalFiles: payload.total_files,
    processedFiles: payload.processed_files,
    failedFiles: payload.failed_files,
    metadata: payload.metadata || {},
    errorMessage: payload.error_message,
    createdAt: payload.created_at,
    updatedAt: payload.updated_at,
    files: Array.isArray(payload.files) ? payload.files.map(normalizeImportFile) : [],
  };
}

function normalizeImportFile(payload = {}) {
  return {
    importFileId: payload.import_file_id,
    importId: payload.import_id,
    googleFileId: payload.google_file_id,
    filename: payload.filename,
    mimeType: payload.mime_type,
    exportMimeType: payload.export_mime_type,
    sizeBytes: payload.size_bytes,
    status: payload.status,
    documentId: payload.document_id,
    metadata: payload.metadata || {},
    errorMessage: payload.error_message,
    createdAt: payload.created_at,
    updatedAt: payload.updated_at,
  };
}

export function getGoogleDriveAuthUrl(apiClient, codeChallenge) {
  return apiClient("/api/v1/google-drive/auth-url", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({code_challenge: codeChallenge}) });
}

export function connectGoogleDrive(apiClient, payload) {
  return apiClient("/api/v1/google-drive/oauth/callback", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload)}).then(normalizeConnection);
}

export function disconnectGoogleDrive(apiClient, version) {
  return apiClient("/api/v1/google-drive/disconnect", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({version})}).then(normalizeConnection);
}

export function getGoogleDriveConnection(apiClient) {
  return apiClient("/api/v1/google-drive/connection", { method: "GET" }).then(normalizeConnection);
}

export function importGoogleDriveFiles(apiClient, { files, folderId = null, metadata = {}, operationId, connectionVersion, signal }) {
  if (!operationId) throw new Error("La importación requiere una clave de operación.");
  return apiClient("/api/v1/google-drive/imports", {
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
  }).then(normalizeImport);
}

function page(payload, normalize, id) {
  if (!payload || !Array.isArray(payload.items) || payload.items.length > 100 ||
      !(payload.next_cursor === null || (typeof payload.next_cursor === "string" && /^[A-Za-z0-9_-]{1,1024}$/.test(payload.next_cursor))) ||
      payload.items.some((item) => !item || typeof item[id] !== "string" || !item[id]) ||
      new Set(payload.items.map((item) => item[id])).size !== payload.items.length ||
      (payload.next_cursor && !payload.items.length)) throw new Error("Respuesta de historial de Drive inválida.");
  return { items: payload.items.map(normalize), nextCursor: payload.next_cursor };
}
export function listGoogleDriveImports(apiClient, { limit = 25, cursor, signal } = {}) {
  const query = new URLSearchParams({ limit: String(limit) });
  if (cursor) query.set("before", cursor);
  return apiClient(`/api/v1/google-drive/imports?${query}`, { method: "GET", signal })
    .then((payload) => page(payload, normalizeImport, "import_id"));
}
export function getGoogleDriveImport(apiClient, importId, signal) {
  return apiClient(`/api/v1/google-drive/imports/${encodeURIComponent(importId)}`, { method: "GET", signal }).then(normalizeImport);
}
export function listGoogleDriveImportFiles(apiClient, importId, { limit = 25, cursor, signal } = {}) {
  const query = new URLSearchParams({ limit: String(limit) });
  if (cursor) query.set("after", cursor);
  return apiClient(`/api/v1/google-drive/imports/${encodeURIComponent(importId)}/files?${query}`, { method: "GET", signal })
    .then((payload) => page(payload, normalizeImportFile, "import_file_id"));
}
