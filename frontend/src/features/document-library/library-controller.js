import {
  addFavoriteDocument, createFolder, getDocumentMarkers, listFavoriteDocuments,
  listFolderDocuments, listFolders, listRecentDocuments, moveDocumentToFolder, removeFavoriteDocument,
} from "./api/document-library.api.js";

const emptyPage = () => ({ items: [], hasMore: false, nextOffset: 0, loading: false, error: "" });

// One controller per API client. Versions discard late responses after refresh, close or disposal.
export function createLibraryController(apiClient) {
  const listeners = new Set();
  const versions = {};
  const busy = new Map();
  let active = true;
  let epoch = 0;
  let visibleIds = [];
  let state = { folders: emptyPage(), recent: emptyPage(), favorites: emptyPage(), content: emptyPage(),
    selectedFolder: null, markers: {}, error: "" };
  const emit = (patch) => {
    if (!active) return;
    state = { ...state, ...patch };
    listeners.forEach((notify) => notify());
  };
  const patchPage = (key, patch) => emit({ [key]: { ...state[key], ...patch } });
  const current = (key, version) => active && versions[key] === version;

  async function load(key, append = false) {
    if (!active || !apiClient || (append && (state[key].loading || !state[key].hasMore))) return false;
    const folderId = state.selectedFolder?.folderId;
    if (key === "content" && !folderId) return false;
    const version = versions[key] = (versions[key] || 0) + 1;
    const offset = append ? state[key].nextOffset : 0;
    patchPage(key, { ...(append ? {} : emptyPage()), loading: true, error: "" });
    try {
      const page = { limit: 50, offset };
      const loaders = { folders: () => listFolders(apiClient, null, page), recent: () => listRecentDocuments(apiClient, page),
        favorites: () => listFavoriteDocuments(apiClient, page), content: () => listFolderDocuments(apiClient, folderId, page) };
      const result = await loaders[key]();
      if (!current(key, version)) return false;
      const id = key === "folders" ? "folderId" : "documentId";
      const items = new Map((append ? state[key].items : []).map((item) => [item[id], item]));
      result.items.forEach((item) => items.set(item[id], item));
      patchPage(key, { items: [...items.values()], hasMore: result.hasMore,
        nextOffset: result.offset + result.items.length, loading: false });
      return true;
    } catch (error) {
      if (current(key, version)) {
        patchPage(key, { loading: false, error: error.message });
        if (key === "content" && error.status === 404) emit({ selectedFolder: null, content: emptyPage(), error: error.message });
      }
      return false;
    }
  }

  async function refreshMarkers(ids = visibleIds) {
    if (!active) return;
    visibleIds = [...new Set(ids)].slice(0, 100);
    const requested = visibleIds;
    const version = versions.markers = (versions.markers || 0) + 1;
    emit({ markers: {} });
    if (!apiClient || !requested.length) return;
    try {
      const items = await getDocumentMarkers(apiClient, requested);
      if (current("markers", version)) {
        const marked = new Map(items.map((item) => [item.documentId, item.isFavorite]));
        emit({ markers: Object.fromEntries(requested.map((id) => [id, marked.get(id) === true])) });
      }
    } catch (error) {
      if (current("markers", version)) emit({ error: error.message });
    }
  }

  async function refreshLibrary(keepError = false) {
    if (!keepError) emit({ error: "" });
    await Promise.all([load("folders"), load("recent"), load("favorites"),
      ...(state.selectedFolder ? [load("content")] : []), refreshMarkers()]);
  }

  function closeFolder() {
    versions.content = (versions.content || 0) + 1;
    emit({ selectedFolder: null, content: emptyPage() });
  }

  async function openFolder(folder) {
    if (!active) return;
    emit({ selectedFolder: folder, content: emptyPage(), error: "" });
    return load("content");
  }

  async function toggleFavorite(document) {
    const id = document?.documentId;
    if (!apiClient || !active || !id || busy.has(id)) return false;
    const operation = epoch;
    const busyToken = Symbol(id);
    busy.set(id, busyToken);
    emit({ error: "" });
    try {
      const markers = await getDocumentMarkers(apiClient, [id]);
      if (!active || operation !== epoch) return false;
      if (!markers.length) throw new Error("El documento ya no está disponible.");
      const marked = markers[0].isFavorite;
      const result = await (marked ? removeFavoriteDocument(apiClient, id) : addFavoriteDocument(apiClient, id));
      if (!active || operation !== epoch) return false;
      if (!marked && result.count !== 1) throw new Error("No se pudo guardar el favorito. Actualiza los permisos del documento.");
      await refreshLibrary(true);
      return true;
    } catch (error) {
      if (active && operation === epoch) {
        await refreshLibrary(true);
        if (active && operation === epoch) emit({ error: error.message });
      }
      return false;
    } finally {
      if (busy.get(id) === busyToken) busy.delete(id);
    }
  }

  async function addFolder(name) {
    if (!apiClient || !active || !name.trim()) return null;
    const operation = epoch;
    emit({ error: "" });
    try {
      const folder = await createFolder(apiClient, { name: name.trim() });
      if (!active || operation !== epoch) return null;
      await refreshLibrary(true);
      return active && operation === epoch ? folder : null;
    } catch (error) {
      if (active && operation === epoch) emit({ error: error.message });
      return null;
    }
  }

  async function moveDocument(document, folderId = null) {
    if (!apiClient || !active || !document?.documentId) return false;
    const operation = epoch;
    emit({ error: "" });
    try {
      const result = await moveDocumentToFolder(apiClient, document.documentId, folderId);
      if (!active || operation !== epoch) return false;
      if (result.success !== true) throw new Error("No se pudo mover el documento.");
      await refreshLibrary(true);
      return active && operation === epoch;
    } catch (error) {
      if (active && operation === epoch) {
        await refreshLibrary(true);
        if (active && operation === epoch) emit({ error: error.message });
      }
      return false;
    }
  }

  return {
    subscribe: (notify) => { listeners.add(notify); return () => listeners.delete(notify); },
    getSnapshot: () => state,
    start: () => { active = true; return refreshLibrary(); },
    dispose: () => { active = false; epoch += 1; Object.keys(versions).forEach((key) => { versions[key] += 1; }); busy.clear(); },
    loadMore: (key) => load(key, true), refreshLibrary, refreshMarkers, openFolder, closeFolder, addFolder, moveDocument, toggleFavorite,
  };
}
