import { useCallback, useEffect, useMemo, useState } from "react";

import {
  addFavoriteDocument,
  createFolder,
  listFavoriteDocuments,
  listFolderDocuments,
  listFolders,
  listRecentDocuments,
  moveDocumentToFolder,
  removeFavoriteDocument,
} from "../api/document-library.api";

export function useDocumentLibrary(apiClient) {
  const [folders, setFolders] = useState([]);
  const [recentDocuments, setRecentDocuments] = useState([]);
  const [favoriteDocuments, setFavoriteDocuments] = useState([]);
  const [folderDocuments, setFolderDocuments] = useState([]);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [selectedFolder, setSelectedFolder] = useState(null);

  const favoriteIds = useMemo(
    () => new Set(favoriteDocuments.map((document) => document.documentId)),
    [favoriteDocuments],
  );

  const refreshLibrary = useCallback(async () => {
    if (!apiClient) return;

    setIsLoading(true);
    setError("");

    try {
      const [nextFolders, nextRecentDocuments, nextFavoriteDocuments] = await Promise.all([
        listFolders(apiClient),
        listRecentDocuments(apiClient, 20),
        listFavoriteDocuments(apiClient),
      ]);
      setFolders(nextFolders);
      setRecentDocuments(nextRecentDocuments);
      setFavoriteDocuments(nextFavoriteDocuments);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsLoading(false);
    }
  }, [apiClient]);

  useEffect(() => {
    refreshLibrary();
  }, [refreshLibrary]);

  async function toggleFavorite(document) {
    if (!apiClient || !document?.documentId) return;

    const wasFavorite = favoriteIds.has(document.documentId);
    setError("");
    setFavoriteDocuments((current) =>
      wasFavorite
        ? current.filter((item) => item.documentId !== document.documentId)
        : [{ ...document }, ...current],
    );

    try {
      if (wasFavorite) {
        await removeFavoriteDocument(apiClient, document.documentId);
      } else {
        await addFavoriteDocument(apiClient, document.documentId);
      }
      await refreshLibrary();
    } catch (requestError) {
      setError(requestError.message);
      await refreshLibrary();
    }
  }

  async function addFolder(name) {
    if (!apiClient) return null;
    const cleanName = name.trim();
    if (!cleanName) return null;

    setError("");
    try {
      const folder = await createFolder(apiClient, { name: cleanName });
      await refreshLibrary();
      return folder;
    } catch (requestError) {
      setError(requestError.message);
      return null;
    }
  }

  async function openFolder(folder) {
    if (!apiClient || !folder?.folderId) return;
    setSelectedFolder(folder);
    setFolderDocuments([]);
    setError("");
    setIsLoading(true);

    try {
      setFolderDocuments(await listFolderDocuments(apiClient, folder.folderId));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsLoading(false);
    }
  }

  function closeFolder() {
    setSelectedFolder(null);
    setFolderDocuments([]);
  }

  async function moveDocument(document, folderId = null) {
    if (!apiClient || !document?.documentId) return false;

    setError("");
    try {
      await moveDocumentToFolder(apiClient, document.documentId, folderId);
      await refreshLibrary();
      if (selectedFolder) {
        setFolderDocuments(await listFolderDocuments(apiClient, selectedFolder.folderId));
      }
      return true;
    } catch (requestError) {
      setError(requestError.message);
      return false;
    }
  }

  return {
    folders,
    folderDocuments,
    recentDocuments,
    favoriteDocuments,
    favoriteIds,
    selectedFolder,
    error,
    isLoading,
    addFolder,
    closeFolder,
    moveDocument,
    openFolder,
    refreshLibrary,
    toggleFavorite,
  };
}
