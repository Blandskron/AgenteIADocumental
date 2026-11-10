import type { MaybeClient } from "@/shared/api/types.ts";
import { toError } from "@/shared/lib/errors.ts";
import type { Transfer, TransferInput } from "./api/transfers.api.ts";
import {
  clearTransferHistory,
  createTransfer,
  listTransfers,
  updateTransfer,
} from "./api/transfers.api.ts";

interface State {
  transfers: Transfer[];
  hasMore: boolean;
  nextOffset: number;
  isLoading: boolean;
  isClearing: boolean;
  error: string;
  warning: string;
}
const empty = (): State => ({
  transfers: [],
  hasMore: false,
  nextOffset: 0,
  isLoading: false,
  isClearing: false,
  error: "",
  warning: "",
});

export function createTransferController(apiClient: MaybeClient) {
  const listeners = new Set<() => void>();
  let state = empty();
  let active = false,
    epoch = 0,
    version = 0;
  const current = (scope: number) => active && scope === epoch;
  const emit = (patch: Partial<State>) => {
    if (active) {
      state = { ...state, ...patch };
      listeners.forEach((notify: () => void) => notify());
    }
  };
  async function load(append = false, preserve = false) {
    if (
      !active ||
      !apiClient ||
      (append && (state.isLoading || !state.hasMore))
    )
      return false;
    const scope = epoch,
      request = ++version;
    const offset = append ? state.nextOffset : 0;
    emit({
      ...(append
        ? {}
        : {
            ...(preserve ? {} : { transfers: [] }),
            hasMore: false,
            nextOffset: 0,
          }),
      isLoading: true,
      error: "",
    });
    try {
      const page = await listTransfers(apiClient, { offset });
      if (!current(scope) || request !== version) return false;
      const rows = new Map(
        (append ? state.transfers : []).map((row) => [row.transferId, row]),
      );
      page.items.forEach((row) => rows.set(row.transferId, row));
      emit({
        transfers: [...rows.values()],
        hasMore: page.hasMore && page.items.length > 0,
        nextOffset: page.nextOffset,
        isLoading: false,
      });
      return true;
    } catch (caughtError) {
      const error = toError(caughtError);
      if (current(scope) && request === version)
        emit({
          isLoading: false,
          error: error?.message || "No se pudo consultar el historial.",
        });
      return false;
    }
  }
  function captureJournal() {
    const scope = epoch;
    async function write(operation: () => Promise<Transfer>) {
      if (!current(scope)) return null;
      if (!apiClient) throw new Error("El historial no está disponible.");
      const row = await operation();
      if (!current(scope)) return null;
      void load();
      return row;
    }
    return {
      isActive: () => current(scope),
      recordTransfer: (payload: TransferInput) =>
        write(() => createTransfer(apiClient, payload)),
      patchTransfer: (id: string, payload: Partial<TransferInput>) =>
        write(() => updateTransfer(apiClient, id, payload)),
      noteWarning: (error: { message?: string }) => {
        if (current(scope))
          emit({
            warning: `No se pudo actualizar el historial. El resultado del archivo se conserva. ${error?.message || ""}`,
          });
      },
    };
  }
  async function clearHistory() {
    if (!active || !apiClient || state.isClearing) return false;
    const scope = epoch;
    emit({ isClearing: true, error: "" });
    try {
      await clearTransferHistory(apiClient);
      if (!current(scope)) return false;
      emit({
        transfers: state.transfers.filter((row) =>
          ["PENDING", "RUNNING"].includes(row.status),
        ),
      });
      return await load(false, true);
    } catch (caughtError) {
      const error = toError(caughtError);
      if (current(scope))
        emit({ error: error?.message || "No se pudo limpiar el historial." });
      return false;
    } finally {
      if (current(scope)) emit({ isClearing: false });
    }
  }
  return {
    subscribe: (notify: () => void) => {
      listeners.add(notify);
      return () => listeners.delete(notify);
    },
    getSnapshot: () => state,
    start: (autoLoad = true) => {
      active = true;
      epoch++;
      version++;
      emit(empty());
      if (autoLoad) void load();
    },
    dispose: () => {
      active = false;
      epoch++;
      version++;
    },
    refreshTransfers: () => load(),
    loadMore: () => load(true),
    clearHistory,
    captureJournal,
    dismissWarning: () => emit({ warning: "" }),
  };
}
