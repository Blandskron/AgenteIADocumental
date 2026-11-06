function normalizeDocument(document = {}) {
  return {
    documentId: document.document_id,
    filename: document.filename || "documento",
    mimeType: document.mime_type || "",
    status: document.status || "UNKNOWN",
    chunkCount: Number(document.chunk_count || 0),
    updatedAt: document.updated_at || "",
    isFavorite: document.is_favorite === true,
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

function normalizePage(payload, normalize) {
  if (!payload || !Array.isArray(payload.items) || !Number.isInteger(payload.limit) || payload.limit < 1 ||
      !Number.isInteger(payload.offset) || payload.offset < 0 || typeof payload.has_more !== "boolean") {
    throw new Error("Respuesta de biblioteca incompatible. Actualiza la aplicación y el servicio juntos.");
  }
  return { items: payload.items.map(normalize), limit: payload.limit, offset: payload.offset, hasMore: payload.has_more };
}

function pageParams({ limit = 50, offset = 0 } = {}) {
  return new URLSearchParams({ limit, offset });
}

export function listFolders(apiClient, parentFolderId = null, page = {}) {
  const params = pageParams(page);
  if (parentFolderId) params.set("parent_folder_id", parentFolderId);

  return apiClient(`/api/v1/folders?${params.toString()}`, {
    method: "GET",
  }).then((payload) => normalizePage(payload, normalizeFolder));
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

export function listFolderDocuments(apiClient, folderId, page = {}) {
  return apiClient(`/api/v1/folders/${encodeURIComponent(folderId)}/documents?${pageParams(page)}`, {
    method: "GET",
  }).then((payload) => normalizePage(payload, normalizeDocument));
}

export function moveDocumentToFolder(apiClient, documentId, folderId = null) {
  return apiClient(`/api/v1/library/documents/${encodeURIComponent(documentId)}/folder`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ folder_id: folderId }),
  });
}

export function listRecentDocuments(apiClient, page = {}) {
  return apiClient(`/api/v1/library/recent?${pageParams(page)}`, {
    method: "GET",
  }).then((payload) => normalizePage(payload, normalizeDocument));
}

export function listFavoriteDocuments(apiClient, page = {}) {
  return apiClient(`/api/v1/library/favorites?${pageParams(page)}`, {
    method: "GET",
  }).then((payload) => normalizePage(payload, normalizeDocument));
}

export function addFavoriteDocument(apiClient, documentId) {
  return apiClient(`/api/v1/library/favorites/${encodeURIComponent(documentId)}`, {
    method: "POST",
  });
}

export function removeFavoriteDocument(apiClient, documentId) {
  return apiClient(`/api/v1/library/favorites/${encodeURIComponent(documentId)}`, {
    method: "DELETE",
  });
}

export function getDocumentMarkers(apiClient, documentIds) {
  return apiClient("/api/v1/library/markers", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_ids: documentIds }),
  }).then((items) => {
    if (!Array.isArray(items)) throw new Error("Respuesta de marcadores incompatible.");
    return items.map((item) => ({ documentId: item.document_id, isFavorite: item.is_favorite === true }));
  });
}
