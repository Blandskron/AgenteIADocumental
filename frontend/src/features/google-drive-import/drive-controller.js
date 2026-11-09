import { importGoogleDriveFiles } from "./api/google-drive-import.api.js";
import { prepareImportAttempt, finishImportAttempt, rejectImportAttempt } from "./import-attempt.js";
import { getImportWarning } from "./import-result.js";

// One lane for import and Picker. Aborting stops waiting, never undoes a server upload.
export function createDriveController({ client, scope, context, changed, prepare = prepareImportAttempt,
  finish = finishImportAttempt, reject = rejectImportAttempt, upload = importGoogleDriveFiles }) {
  let active = true, epoch = 0, task = null;
  function cancel(announce = true) {
    epoch++;
    task?.abort();
    task = null;
    if (active) changed({ busy: false, error: announce ? "Se dejó de esperar. El servidor puede continuar; consulta la importación pendiente antes de repetir." : "", success: "" });
  }
  async function run(work) {
    if (!active || task) return;
    const snapshot = context(), generation = ++epoch, abort = new AbortController();
    task = abort;
    const current = () => active && epoch === generation && !abort.signal.aborted && context() === snapshot;
    changed({ busy: true, error: "", success: "" });
    try { await work(abort.signal, current); }
    catch (error) { if (current()) changed({ busy: true, error: error.message, success: "" }); }
    finally {
      if (epoch === generation) {
        task = null;
        if (current()) changed({ busy: false });
      }
    }
  }
  return {
    start() { active = true; },
    stop() { active = false; cancel(false); },
    cancel,
    import(input, connectionVersion, completed, connectionChanged) {
      return run(async (signal, current) => {
        const files = input.files;
        if (!files?.length || files.length > 25 || files.some((file) => !/^[A-Za-z0-9_-]{1,128}$/.test(file.fileId || file.id || "")) ||
            new Set(files.map((file) => file.fileId || file.id)).size !== files.length) throw new Error("Selecciona entre 1 y 25 archivos distintos con IDs válidos.");
        const attempt = prepare(scope, input, connectionVersion);
        let result;
        try { result = await upload(client, { ...input, ...attempt, signal }); }
        catch (error) {
          if (!current()) return;
          reject(scope, attempt.operationId, error);
          if (error.payload?.code === "import_connection_changed") await connectionChanged?.();
          if (current()) throw error;
          return;
        }
        if (!current()) return;
        finish(scope, attempt.operationId, result);
        const warning = result.status === "REVIEW_REQUIRED" ? "La carga tiene un resultado incierto. Revisa el historial antes de reintentar." : getImportWarning(result);
        changed({ error: warning, success: warning ? "" : "Documentos enviados a procesamiento." });
        if (result.status !== "REVIEW_REQUIRED") await completed?.(result, current);
      });
    },
    picker(open, selected) {
      return run(async (signal, current) => {
        const files = await open(signal);
        if (current() && files.length) selected(files);
      });
    },
  };
}
