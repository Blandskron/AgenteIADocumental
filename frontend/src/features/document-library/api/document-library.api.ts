import type { MaybeClient } from "@/shared/api/types.ts";
import { requireClient } from "@/shared/api/types.ts";
interface DocumentDto {
  document_id?: string;
  filename?: string;
  mime_type?: string;
  status?: string;
  chunk_count?: number;
  updated_at?: string;
  is_favorite?: boolean;
}
interface FolderDto {
  folder_id?: string;
  name?: string;
  parent_folder_id?: string;
  owner_user_id?: string;
  metadata?: Record<string, unknown>;
  document_count?: number;
  created_at?: string;
  updated_at?: string;
}
interface PageDto<T> {
  items: T[];
  limit: number;
  offset: number;
  has_more: boolean;
}
function normalizeDocument(document: DocumentDto = {}) {
  return {
    documentId: document.document_id || "",
    filename: document.filename || "documento",
    mimeType: document.mime_type || "",
    status: document.status || "UNKNOWN",
    chunkCount: Number(document.chunk_count || 0),
    updatedAt: document.updated_at || "",
    isFavorite: document.is_favorite === true,
  };
}

function normalizeFolder(folder: FolderDto = {}) {
  return {
    folderId: folder.folder_id || "",
    name: folder.name || "Carpeta",
    parentFolderId: folder.parent_folder_id || null,
    ownerUserId: folder.owner_user_id || "",
    metadata: folder.metadata || {},
    documentCount: Number(folder.document_count ?? 0),
    createdAt: folder.created_at || "",
    updatedAt: folder.updated_at || "",
  };
}

function normalizePage<T, R>(payload: PageDto<T>, normalize: (value: T) => R) {
  if (
    !payload ||
    !Array.isArray(payload.items) ||
    !Number.isInteger(payload.limit) ||
    payload.limit < 1 ||
    !Number.isInteger(payload.offset) ||
    payload.offset < 0 ||
    typeof payload.has_more !== "boolean"
  ) {
    throw new Error(
      "Respuesta de biblioteca incompatible. Actualiza la aplicación y el servicio juntos.",
    );
  }
  return {
    items: payload.items.map(normalize),
    limit: payload.limit,
    offset: payload.offset,
    hasMore: payload.has_more,
  };
}

function pageParams({ limit = 50, offset = 0 } = {}) {
  return new URLSearchParams({ limit: String(limit), offset: String(offset) });
}

export function listFolders(
  apiClient: MaybeClient,
  parentFolderId: string | null = null,
  page = {},
) {
  const params = pageParams(page);
  if (parentFolderId) params.set("parent_folder_id", parentFolderId);

  return requireClient(apiClient)<PageDto<FolderDto>>(
    `/api/v1/folders?${params.toString()}`,
    {
      method: "GET",
    },
  ).then((payload) => normalizePage(payload, normalizeFolder));
}

export function createFolder(
  apiClient: MaybeClient,
  {
    name,
    parentFolderId = null,
    metadata = {},
  }: {
    name: string;
    parentFolderId?: string | null;
    metadata?: Record<string, unknown>;
  },
) {
  return requireClient(apiClient)<Parameters<typeof normalizeFolder>[0]>(
    "/api/v1/folders",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        parent_folder_id: parentFolderId,
        metadata,
      }),
    },
  ).then(normalizeFolder);
}

export function listFolderDocuments(
  apiClient: MaybeClient,
  folderId: string,
  page = {},
) {
  return requireClient(apiClient)<PageDto<DocumentDto>>(
    `/api/v1/folders/${encodeURIComponent(folderId)}/documents?${pageParams(page)}`,
    {
      method: "GET",
    },
  ).then((payload) => normalizePage(payload, normalizeDocument));
}

export function moveDocumentToFolder(
  apiClient: MaybeClient,
  documentId: string,
  folderId: string | null = null,
) {
  return requireClient(apiClient)<{ success: boolean }>(
    `/api/v1/library/documents/${encodeURIComponent(documentId)}/folder`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ folder_id: folderId }),
    },
  );
}

export function listRecentDocuments(apiClient: MaybeClient, page = {}) {
  return requireClient(apiClient)<PageDto<DocumentDto>>(
    `/api/v1/library/recent?${pageParams(page)}`,
    {
      method: "GET",
    },
  ).then((payload) => normalizePage(payload, normalizeDocument));
}

export function listFavoriteDocuments(apiClient: MaybeClient, page = {}) {
  return requireClient(apiClient)<PageDto<DocumentDto>>(
    `/api/v1/library/favorites?${pageParams(page)}`,
    {
      method: "GET",
    },
  ).then((payload) => normalizePage(payload, normalizeDocument));
}

export function addFavoriteDocument(
  apiClient: MaybeClient,
  documentId: string,
) {
  return requireClient(apiClient)<{ count: number }>(
    `/api/v1/library/favorites/${encodeURIComponent(documentId)}`,
    {
      method: "POST",
    },
  );
}

export function removeFavoriteDocument(
  apiClient: MaybeClient,
  documentId: string,
) {
  return requireClient(apiClient)<{ count: number }>(
    `/api/v1/library/favorites/${encodeURIComponent(documentId)}`,
    {
      method: "DELETE",
    },
  );
}

export function getDocumentMarkers(
  apiClient: MaybeClient,
  documentIds: string[],
) {
  return requireClient(apiClient)<
    { document_id: string; is_favorite: boolean }[]
  >("/api/v1/library/markers", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_ids: documentIds }),
  }).then((items) => {
    if (!Array.isArray(items))
      throw new Error("Respuesta de marcadores incompatible.");
    return items.map((item) => ({
      documentId: item.document_id || "",
      isFavorite: item.is_favorite === true,
    }));
  });
}
