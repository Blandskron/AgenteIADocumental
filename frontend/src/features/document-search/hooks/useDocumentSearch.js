import { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import { createSearchController } from "../search-controller.js";

export function useDocumentSearch(apiClient) {
  const controller = useMemo(() => createSearchController(apiClient), [apiClient]);
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot);
  const [filters, setFilters] = useState({ client: apiClient, query: "", status: "PROCESSED" });
  const current = filters.client === apiClient ? filters : { client: apiClient, query: "", status: "PROCESSED" };
  useEffect(() => { controller.start(); return () => controller.dispose(); }, [controller]);
  return {
    ...state, query: current.query, status: current.status,
    setQuery: (query) => setFilters({ ...current, query }),
    setStatus: (status) => setFilters({ ...current, status }),
    runSearch: (next = {}) => controller.runSearch({ query: current.query, status: current.status, ...next }),
  };
}
