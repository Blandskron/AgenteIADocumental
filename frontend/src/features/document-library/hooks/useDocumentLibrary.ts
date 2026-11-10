import type { DocumentItem } from "@/entities/document/model/types.ts";
import { createLibraryController } from "@/features/document-library/library-controller.ts";
import type { MaybeClient } from "@/shared/api/types.ts";
import { useEffect, useMemo, useSyncExternalStore } from "react";

export function useDocumentLibrary(
  apiClient: MaybeClient,
  visibleDocuments: DocumentItem[] = [],
) {
  const controller = useMemo(
    () => createLibraryController(apiClient),
    [apiClient],
  );
  const state = useSyncExternalStore(
    controller.subscribe,
    controller.getSnapshot,
  );
  useEffect(() => {
    controller.start();
    return () => controller.dispose();
  }, [controller]);
  const visibleKey = JSON.stringify(
    visibleDocuments.map((item) => item.documentId),
  );
  useEffect(() => {
    controller.refreshMarkers(JSON.parse(visibleKey));
  }, [controller, visibleKey]);

  const known = new Map(
    [
      ...state.recent.items,
      ...state.content.items,
      ...state.favorites.items,
    ].map((document) => [document.documentId, document.isFavorite]),
  );
  Object.entries(state.markers).forEach(([id, marked]) =>
    known.set(id, marked),
  );
  return {
    ...controller,
    folders: state.folders.items,
    recentDocuments: state.recent.items,
    favoriteDocuments: state.favorites.items,
    folderDocuments: state.content.items,
    selectedFolder: state.selectedFolder,
    favoriteIds: new Set(
      [...known].filter(([, marked]) => marked).map(([id]) => id),
    ),
    pages: {
      folders: state.folders,
      recent: state.recent,
      favorites: state.favorites,
      content: state.content,
    },
    error:
      state.error ||
      [state.folders, state.recent, state.favorites, state.content].find(
        (page) => page.error,
      )?.error ||
      "",
    isLoading: [
      state.folders,
      state.recent,
      state.favorites,
      state.content,
    ].some((page) => page.loading),
  };
}
