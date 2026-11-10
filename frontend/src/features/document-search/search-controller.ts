import type {
  DocumentItem,
  SearchFilters,
} from "@/entities/document/model/types.ts";
import type { MaybeClient } from "@/shared/api/types.ts";
import { toError } from "@/shared/lib/errors.ts";
import { searchDocuments } from "./api/document-search.api.ts";

export function createSearchController(apiClient: MaybeClient) {
  let active = true,
    version = 0;
  let state: {
    documents: DocumentItem[];
    total: number;
    error: string;
    isLoading: boolean;
  } = { documents: [], total: 0, error: "", isLoading: false };
  const listeners = new Set<() => void>();
  function emit(patch: Partial<typeof state>) {
    if (!active) return;
    state = { ...state, ...patch };
    listeners.forEach((notify: () => void) => notify());
  }
  async function runSearch(filters: SearchFilters = {}) {
    if (!active || !apiClient) return;
    const request = ++version;
    emit({ documents: [], total: 0, error: "", isLoading: true });
    try {
      const response = await searchDocuments(apiClient, filters);
      if (active && request === version)
        emit({
          documents: response.items,
          total: response.total,
          isLoading: false,
        });
    } catch (caughtError) {
      const error = toError(caughtError);
      if (active && request === version)
        emit({ error: error.message, isLoading: false });
    }
  }
  return {
    subscribe: (notify: () => void) => {
      listeners.add(notify);
      return () => listeners.delete(notify);
    },
    getSnapshot: () => state,
    runSearch,
    start: () => {
      active = true;
      return runSearch({ status: "PROCESSED" });
    },
    dispose: () => {
      active = false;
      version += 1;
    },
  };
}
