import type { MaybeClient } from "@/shared/api/types.ts";
import { toError } from "@/shared/lib/errors.ts";
import type { PdfExport, PdfInput } from "./api/document-export.api.ts";
import {
  createChatMessagePdf,
  deleteExport,
  downloadExport,
  listExports,
} from "./api/document-export.api.ts";
import { savePdf } from "./download-pdf.ts";

interface State {
  items: PdfExport[];
  nextCursor: string | null;
  loading: boolean;
  busyKey: string;
  messageKey: string;
  error: string;
  success: string;
}
const initial = (): State => ({
  items: [],
  nextCursor: null,
  loading: false,
  busyKey: "",
  messageKey: "",
  error: "",
  success: "",
});
const errorText = (error: { status?: number; message?: string }) =>
  messages[error.status || 0] ||
  error.message ||
  "No se pudo completar la operación PDF.";
const messages: Record<number, string> = {
  409: "El PDF requiere revisión o la operación está en conflicto. Actualiza el historial.",
  410: "El PDF expiró. Genera una nueva exportación.",
  413: "Reduce la respuesta o las fuentes: se superaron los límites del PDF.",
  404: "El PDF ya no está disponible.",
  503: "El servicio está ocupado. Inténtalo de nuevo.",
};

export function createExportController(
  client: MaybeClient,
  { save = savePdf, uuid = () => crypto.randomUUID() } = {},
) {
  let state = initial(),
    active = false,
    epoch = 0,
    version = 0,
    read: AbortController | null = null,
    write: AbortController | null = null,
    retry: {
      snapshot: string;
      messageKey: string;
      operationKey: string;
      exported: PdfExport | null;
    } | null = null,
    loaded = false;
  const listeners = new Set<() => void>();
  const current = (generation: number) => active && generation === epoch;
  const emit = (patch: Partial<State>) => {
    if (active) {
      state = { ...state, ...patch };
      listeners.forEach((fn: () => void) => fn());
    }
  };
  async function load(append = false) {
    if (!active || !client || (append && (read || !state.nextCursor)))
      return false;
    read?.abort();
    const generation = epoch,
      request = ++version,
      controller = new AbortController();
    const cursor = append ? state.nextCursor : null;
    read = controller;
    loaded = true;
    emit({
      loading: true,
      error: "",
      ...(append ? {} : { items: [], nextCursor: null }),
    });
    try {
      const page = await listExports(client, {
        before: cursor,
        signal: controller.signal,
      });
      if (!current(generation) || request !== version) return false;
      if (
        page.nextCursor &&
        (page.nextCursor === cursor || page.items.length === 0)
      )
        throw new Error("El historial no avanzó de página.");
      const items = new Map(
        (append ? state.items : []).map((row) => [row.exportId, row]),
      );
      page.items.forEach((row) => items.set(row.exportId, row));
      emit({ items: [...items.values()], nextCursor: page.nextCursor });
      return true;
    } catch (caughtError) {
      const error = toError(caughtError);
      if (
        current(generation) &&
        request === version &&
        error.name !== "AbortError"
      )
        emit({ error: errorText(error) });
      return false;
    } finally {
      if (current(generation) && read === controller) {
        read = null;
        emit({ loading: false });
      }
    }
  }
  async function operate(
    key: string,
    messageKey: string,
    operation: (signal: AbortSignal, live: () => boolean) => Promise<boolean>,
  ) {
    if (!active || !client || write) return false;
    const generation = epoch,
      controller = new AbortController();
    write = controller;
    emit({ busyKey: key, messageKey, error: "", success: "" });
    try {
      const succeeded = await operation(controller.signal, () =>
        current(generation),
      );
      if (!current(generation)) return false;
      if (succeeded) emit({ success: "Operación PDF completada." });
      return succeeded;
    } catch (caughtError) {
      const error = toError(caughtError);
      if (current(generation) && error.name !== "AbortError") {
        if (error.status === 410 || error.status === 404) retry = null;
        if (loaded && [404, 410].includes(error.status)) void load();
        emit({ error: errorText(error) });
      }
      return false;
    } finally {
      if (current(generation) && write === controller) {
        write = null;
        emit({ busyKey: "", messageKey: "" });
      }
    }
  }
  function exportMessage(messageKey: string, payload: PdfInput) {
    return operate("create:" + messageKey, messageKey, async (signal, live) => {
      const snapshot = JSON.stringify(payload);
      if (
        !retry ||
        retry.snapshot !== snapshot ||
        retry.messageKey !== messageKey
      ) {
        retry = { snapshot, messageKey, operationKey: uuid(), exported: null };
      }
      const attempt = retry;
      if (!attempt.exported)
        attempt.exported = await createChatMessagePdf(
          client,
          JSON.parse(snapshot),
          { signal, operationKey: attempt.operationKey },
        );
      if (!live()) return false;
      const file = await downloadExport(
        client,
        attempt.exported.exportId,
        signal,
      );
      if (!live()) return false;
      const saved = await save(file, attempt.exported.filename, live);
      if (!live()) return false;
      if (saved) {
        retry = null;
        if (loaded) void load();
      }
      return saved;
    });
  }
  function cancelPending() {
    epoch++;
    version++;
    read?.abort();
    write?.abort();
    read = null;
    write = null;
    emit({
      loading: false,
      busyKey: "",
      messageKey: "",
      error: "",
      success: "",
    });
  }
  return {
    subscribe: (fn: () => void) => {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    getSnapshot: () => state,
    start() {
      active = true;
      epoch++;
      loaded = false;
      emit(initial());
    },
    dispose() {
      active = false;
      cancelPending();
    },
    cancelPending,
    exportMessage,
    refresh: () => load(),
    loadMore: () => load(true),
    download(row: PdfExport) {
      return operate("download:" + row.exportId, "", async (signal, live) => {
        const file = await downloadExport(client, row.exportId, signal);
        if (!live()) return false;
        return save(file, row.filename, live);
      });
    },
    remove(row: PdfExport) {
      return operate("delete:" + row.exportId, "", async (signal, live) => {
        await deleteExport(client, row.exportId, signal);
        if (!live()) return false;
        void load();
        return true;
      });
    },
  };
}
