function normalizeDocument(document = {}) {
  return {
    documentId: document.document_id,
    filename: document.filename || "documento",
    mimeType: document.mime_type || "",
    status: document.status || "UNKNOWN",
    chunkCount: Number(document.chunk_count || 0),
    updatedAt: document.updated_at || "",
  };
}

function normalizeFolder(folder = {}) {
  return {
    folderId: folder.folder_id,
    name: folder.name || "Carpeta",
    parentFolderId: folder.parent_folder_id || null,
    ownerUserId: folder.owner_user_id || "",
    metadata: folder.metadata || {},
    documentCount: Number(folder.document_count ?? 0),
    createdAt: folder.created_at || "",
    updatedAt: folder.updated_at || "",
  };
}

export function listFolders(apiClient, parentFolderId = null) {
  const params = new URLSearchParams();
  if (parentFolderId) params.set("parent_folder_id", parentFolderId);

  return apiClient(`/api/v1/folders?${params.toString()}`, {
    method: "GET",
  }).then((payload) => (Array.isArray(payload) ? payload.map(normalizeFolder) : []));
}

export function createFolder(apiClient, { name, parentFolderId = null, metadata = {} }) {
  return apiClient("/api/v1/folders", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name,
      parent_folder_id: parentFolderId,
      metadata,
    }),
  }).then(normalizeFolder);
}

export function listFolderDocuments(apiClient, folderId) {
  return apiClient(`/api/v1/folders/${folderId}/documents`, {
    method: "GET",
  }).then((payload) => (Array.isArray(payload) ? payload.map(normalizeDocument) : []));
}

export function moveDocumentToFolder(apiClient, documentId, folderId = null) {
  return apiClient(`/api/v1/library/documents/${documentId}/folder`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ folder_id: folderId }),
  });
}

export function listRecentDocuments(apiClient, limit = 20) {
  return apiClient(`/api/v1/library/recent?limit=${limit}`, {
    method: "GET",
  }).then((payload) => (Array.isArray(payload) ? payload.map(normalizeDocument) : []));
}

export function listFavoriteDocuments(apiClient) {
  return apiClient("/api/v1/library/favorites", {
    method: "GET",
  }).then((payload) => (Array.isArray(payload) ? payload.map(normalizeDocument) : []));
}

export function addFavoriteDocument(apiClient, documentId) {
  return apiClient(`/api/v1/library/favorites/${documentId}`, {
    method: "POST",
  });
}

export function removeFavoriteDocument(apiClient, documentId) {
  return apiClient(`/api/v1/library/favorites/${documentId}`, {
    method: "DELETE",
  });
}
