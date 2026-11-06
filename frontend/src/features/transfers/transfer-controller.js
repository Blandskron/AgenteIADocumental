import { clearTransferHistory, createTransfer, listTransfers, updateTransfer } from "./api/transfers.api.js";

const empty = () => ({ transfers: [], hasMore: false, nextOffset: 0, isLoading: false, isClearing: false, error: "", warning: "" });

export function createTransferController(apiClient) {
  const listeners = new Set();
  let state = empty();
  let active = false, epoch = 0, version = 0;
  const current = (scope) => active && scope === epoch;
  const emit = (patch) => { if (active) { state = { ...state, ...patch }; listeners.forEach((notify) => notify()); } };
  async function load(append = false, preserve = false) {
    if (!active || !apiClient || (append && (state.isLoading || !state.hasMore))) return false;
    const scope = epoch, request = ++version;
    const offset = append ? state.nextOffset : 0;
    emit({ ...(append ? {} : { ...(preserve ? {} : { transfers: [] }), hasMore: false, nextOffset: 0 }), isLoading: true, error: "" });
    try {
      const page = await listTransfers(apiClient, { offset });
      if (!current(scope) || request !== version) return false;
      const rows = new Map((append ? state.transfers : []).map((row) => [row.transferId, row]));
      page.items.forEach((row) => rows.set(row.transferId, row));
      emit({ transfers: [...rows.values()], hasMore: page.hasMore && page.items.length > 0, nextOffset: page.nextOffset, isLoading: false });
      return true;
    } catch (error) {
      if (current(scope) && request === version) emit({ isLoading: false, error: error?.message || "No se pudo consultar el historial." });
      return false;
    }
  }
  function captureJournal() {
    const scope = epoch;
    async function write(operation) {
      if (!current(scope)) return null;
      if (!apiClient) throw new Error("El historial no está disponible.");
      const row = await operation();
      if (!current(scope)) return null;
      void load();
      return row;
    }
    return {
      isActive: () => current(scope),
      recordTransfer: (payload) => write(() => createTransfer(apiClient, payload)),
      patchTransfer: (id, payload) => write(() => updateTransfer(apiClient, id, payload)),
      noteWarning: (error) => {
        if (current(scope)) emit({ warning: `No se pudo actualizar el historial. El resultado del archivo se conserva. ${error?.message || ""}` });
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
      emit({ transfers: state.transfers.filter((row) => ["PENDING", "RUNNING"].includes(row.status)) });
      return await load(false, true);
    } catch (error) {
      if (current(scope)) emit({ error: error?.message || "No se pudo limpiar el historial." });
      return false;
    } finally { if (current(scope)) emit({ isClearing: false }); }
  }
  return {
    subscribe: (notify) => { listeners.add(notify); return () => listeners.delete(notify); }, getSnapshot: () => state,
    start: (autoLoad = true) => { active = true; epoch++; version++; emit(empty()); if (autoLoad) void load(); },
    dispose: () => { active = false; epoch++; version++; },
    refreshTransfers: () => load(), loadMore: () => load(true), clearHistory, captureJournal,
    dismissWarning: () => emit({ warning: "" }),
  };
}
