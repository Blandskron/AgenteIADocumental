import { searchDocuments } from "./api/document-search.api.js";

export function createSearchController(apiClient) {
  let active = true, version = 0;
  let state = { documents: [], total: 0, error: "", isLoading: false };
  const listeners = new Set();
  function emit(patch) {
    if (!active) return;
    state = { ...state, ...patch };
    listeners.forEach((notify) => notify());
  }
  async function runSearch(filters = {}) {
    if (!active || !apiClient) return;
    const request = ++version;
    emit({ documents: [], total: 0, error: "", isLoading: true });
    try {
      const response = await searchDocuments(apiClient, filters);
      if (active && request === version) emit({ documents: response.items, total: response.total, isLoading: false });
    } catch (error) {
      if (active && request === version) emit({ error: error.message, isLoading: false });
    }
  }
  return {
    subscribe: (notify) => { listeners.add(notify); return () => listeners.delete(notify); },
    getSnapshot: () => state, runSearch,
    start: () => { active = true; return runSearch({ status: "PROCESSED" }); },
    dispose: () => { active = false; version += 1; },
  };
}
