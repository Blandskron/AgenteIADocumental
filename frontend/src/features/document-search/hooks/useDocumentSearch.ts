import type { SearchFilters } from "@/entities/document/model/types.ts";
import { createSearchController } from "@/features/document-search/search-controller.ts";
import type { MaybeClient } from "@/shared/api/types.ts";
import { useEffect, useMemo, useState, useSyncExternalStore } from "react";

export function useDocumentSearch(apiClient: MaybeClient) {
  const controller = useMemo(
    () => createSearchController(apiClient),
    [apiClient],
  );
  const state = useSyncExternalStore(
    controller.subscribe,
    controller.getSnapshot,
  );
  const [filters, setFilters] = useState({
    client: apiClient,
    query: "",
    status: "PROCESSED",
  });
  const current =
    filters.client === apiClient
      ? filters
      : { client: apiClient, query: "", status: "PROCESSED" };
  useEffect(() => {
    controller.start();
    return () => controller.dispose();
  }, [controller]);
  return {
    ...state,
    query: current.query,
    status: current.status,
    setQuery: (query: string) => setFilters({ ...current, query }),
    setStatus: (status: string) => setFilters({ ...current, status }),
    runSearch: (next: SearchFilters = {}) =>
      controller.runSearch({
        query: current.query,
        status: current.status,
        ...next,
      }),
  };
}
