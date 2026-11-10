import type { DocumentItem, Folder } from "@/entities/document/model/types.ts";
import type { MaybeClient } from "@/shared/api/types.ts";
import { toError } from "@/shared/lib/errors.ts";
import {
  addFavoriteDocument,
  createFolder,
  getDocumentMarkers,
  listFavoriteDocuments,
  listFolderDocuments,
  listFolders,
  listRecentDocuments,
  moveDocumentToFolder,
  removeFavoriteDocument,
} from "./api/document-library.api.ts";
export interface LibraryPage<T> {
  items: T[];
  hasMore: boolean;
  nextOffset: number;
  loading: boolean;
  error: string;
}
type PageKey = "folders" | "recent" | "favorites" | "content";
interface State {
  folders: LibraryPage<Folder>;
  recent: LibraryPage<DocumentItem>;
  favorites: LibraryPage<DocumentItem>;
  content: LibraryPage<DocumentItem>;
  selectedFolder: Folder | null;
  markers: Record<string, boolean>;
  error: string;
}

const emptyPage = <T>(): LibraryPage<T> => ({
  items: [],
  hasMore: false,
  nextOffset: 0,
  loading: false,
  error: "",
});

// One controller per API client. Versions discard late responses after refresh, close or disposal.
export function createLibraryController(apiClient: MaybeClient) {
  const listeners = new Set<() => void>();
  const versions: Record<string, number> = {};
  const busy = new Map<string, symbol>();
  let active = true;
  let epoch = 0;
  let visibleIds: string[] = [];
  let state: State = {
    folders: emptyPage(),
    recent: emptyPage(),
    favorites: emptyPage(),
    content: emptyPage(),
    selectedFolder: null,
    markers: {},
    error: "",
  };
  const emit = (patch: Partial<State>) => {
    if (!active) return;
    state = { ...state, ...patch };
    listeners.forEach((notify) => notify());
  };
  const patchPage = (
    key: PageKey,
    patch: Partial<LibraryPage<Folder | DocumentItem>>,
  ) => emit({ [key]: { ...state[key], ...patch } });
  const current = (key: string, version: number) =>
    active && versions[key] === version;

  async function load(key: PageKey, append = false) {
    if (
      !active ||
      !apiClient ||
      (append && (state[key].loading || !state[key].hasMore))
    )
      return false;
    const folderId = state.selectedFolder?.folderId;
    if (key === "content" && !folderId) return false;
    const version = (versions[key] = (versions[key] || 0) + 1);
    const offset = append ? state[key].nextOffset : 0;
    patchPage(key, {
      ...(append ? {} : emptyPage()),
      loading: true,
      error: "",
    });
    try {
      const page = { limit: 50, offset };
      const loaders = {
        folders: () => listFolders(apiClient, null, page),
        recent: () => listRecentDocuments(apiClient, page),
        favorites: () => listFavoriteDocuments(apiClient, page),
        content: () => listFolderDocuments(apiClient, folderId!, page),
      };
      const result = await loaders[key]();
      if (!current(key, version)) return false;
      const id = (item: Folder | DocumentItem) =>
        "folderId" in item ? item.folderId : item.documentId;
      const items = new Map(
        (append ? state[key].items : []).map((item) => [id(item), item]),
      );
      result.items.forEach((item) => items.set(id(item), item));
      patchPage(key, {
        items: [...items.values()],
        hasMore: result.hasMore,
        nextOffset: result.offset + result.items.length,
        loading: false,
      });
      return true;
    } catch (caughtError) {
      const error = toError(caughtError);
      if (current(key, version)) {
        patchPage(key, { loading: false, error: error.message });
        if (key === "content" && error.status === 404)
          emit({
            selectedFolder: null,
            content: emptyPage(),
            error: error.message,
          });
      }
      return false;
    }
  }

  async function refreshMarkers(ids = visibleIds) {
    if (!active) return;
    visibleIds = [...new Set(ids)].slice(0, 100);
    const requested = visibleIds;
    const version = (versions.markers = (versions.markers || 0) + 1);
    emit({ markers: {} });
    if (!apiClient || !requested.length) return;
    try {
      const items = await getDocumentMarkers(apiClient, requested);
      if (current("markers", version)) {
        const marked = new Map(
          items.map((item) => [item.documentId, item.isFavorite]),
        );
        emit({
          markers: Object.fromEntries(
            requested.map((id) => [id, marked.get(id) === true]),
          ),
        });
      }
    } catch (caughtError) {
      const error = toError(caughtError);
      if (current("markers", version)) emit({ error: error.message });
    }
  }

  async function refreshLibrary(keepError = false) {
    if (!keepError) emit({ error: "" });
    await Promise.all([
      load("folders"),
      load("recent"),
      load("favorites"),
      ...(state.selectedFolder ? [load("content")] : []),
      refreshMarkers(),
    ]);
  }

  function closeFolder() {
    versions.content = (versions.content || 0) + 1;
    emit({ selectedFolder: null, content: emptyPage() });
  }

  async function openFolder(folder: Folder) {
    if (!active) return;
    emit({ selectedFolder: folder, content: emptyPage(), error: "" });
    return load("content");
  }

  async function toggleFavorite(document: DocumentItem) {
    const id = document?.documentId;
    if (!apiClient || !active || !id || busy.has(id)) return false;
    const operation = epoch;
    const busyToken = Symbol(id);
    busy.set(id, busyToken);
    emit({ error: "" });
    try {
      const markers = await getDocumentMarkers(apiClient, [id]);
      if (!active || operation !== epoch) return false;
      if (!markers.length)
        throw new Error("El documento ya no está disponible.");
      const marked = markers[0].isFavorite;
      const result = await (marked
        ? removeFavoriteDocument(apiClient, id)
        : addFavoriteDocument(apiClient, id));
      if (!active || operation !== epoch) return false;
      if (!marked && result.count !== 1)
        throw new Error(
          "No se pudo guardar el favorito. Actualiza los permisos del documento.",
        );
      await refreshLibrary(true);
      return true;
    } catch (caughtError) {
      const error = toError(caughtError);
      if (active && operation === epoch) {
        await refreshLibrary(true);
        if (active && operation === epoch) emit({ error: error.message });
      }
      return false;
    } finally {
      if (busy.get(id) === busyToken) busy.delete(id);
    }
  }

  async function addFolder(name: string) {
    if (!apiClient || !active || !name.trim()) return null;
    const operation = epoch;
    emit({ error: "" });
    try {
      const folder = await createFolder(apiClient, { name: name.trim() });
      if (!active || operation !== epoch) return null;
      await refreshLibrary(true);
      return active && operation === epoch ? folder : null;
    } catch (caughtError) {
      const error = toError(caughtError);
      if (active && operation === epoch) emit({ error: error.message });
      return null;
    }
  }

  async function moveDocument(
    document: DocumentItem,
    folderId: string | null = null,
  ) {
    if (!apiClient || !active || !document?.documentId) return false;
    const operation = epoch;
    emit({ error: "" });
    try {
      const result = await moveDocumentToFolder(
        apiClient,
        document.documentId,
        folderId,
      );
      if (!active || operation !== epoch) return false;
      if (result.success !== true)
        throw new Error("No se pudo mover el documento.");
      await refreshLibrary(true);
      return active && operation === epoch;
    } catch (caughtError) {
      const error = toError(caughtError);
      if (active && operation === epoch) {
        await refreshLibrary(true);
        if (active && operation === epoch) emit({ error: error.message });
      }
      return false;
    }
  }

  return {
    subscribe: (notify: () => void) => {
      listeners.add(notify);
      return () => listeners.delete(notify);
    },
    getSnapshot: () => state,
    start: () => {
      active = true;
      return refreshLibrary();
    },
    dispose: () => {
      active = false;
      epoch += 1;
      Object.keys(versions).forEach((key) => {
        versions[key] += 1;
      });
      busy.clear();
    },
    loadMore: (key: PageKey) => load(key, true),
    refreshLibrary,
    refreshMarkers,
    openFolder,
    closeFolder,
    addFolder,
    moveDocument,
    toggleFavorite,
  };
}
