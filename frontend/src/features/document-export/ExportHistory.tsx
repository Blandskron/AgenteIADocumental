import { ModalDialog } from "@/shared/components/ModalDialog.tsx";
import { useId } from "react";
import type { useExports } from "./useExports.ts";

export function ExportHistory({
  isOpen,
  onClose,
  exports,
}: {
  isOpen: boolean;
  onClose: () => void;
  exports: ReturnType<typeof useExports>;
}) {
  const title = useId();
  if (!isOpen) return null;
  const labels: Record<string, string> = {
    COMPLETED: "Disponible",
    EXPIRED: "Expirado",
    MIGRATION_REQUIRED: "Requiere revisión",
  };
  return (
    <ModalDialog
      className="export-history"
      aria-labelledby={title}
      onClose={onClose}
    >
      <h2 id={title}>Mis PDFs</h2>
      <button
        type="button"
        onClick={onClose}
        autoFocus
        aria-label="Cerrar historial PDF"
      >
        Cerrar
      </button>
      <p>
        Se conservan durante 30 días. Eliminar libera espacio; los archivos
        heredados se conservan para revisión.
      </p>
      {exports.error && <p role="alert">{exports.error}</p>}
      {exports.success && <p role="status">{exports.success}</p>}
      {exports.loading && <p role="status">Cargando PDFs...</p>}
      {!exports.loading && exports.items.length === 0 && (
        <p>No hay PDFs guardados.</p>
      )}
      <ul>
        {exports.items.map((row) => (
          <li key={row.exportId}>
            <strong>{row.title}</strong>{" "}
            <span>
              {labels[row.status] || "No disponible"} ·{" "}
              {Math.ceil(row.fileSizeBytes / 1024)} KiB
            </span>
            <div>
              <button
                type="button"
                disabled={
                  Boolean(exports.busyKey) || row.status !== "COMPLETED"
                }
                onClick={() => exports.controller.download(row)}
                aria-label={`Descargar ${row.title}`}
              >
                Descargar PDF
              </button>
              <button
                type="button"
                disabled={Boolean(exports.busyKey)}
                onClick={() => exports.controller.remove(row)}
                aria-label={`Eliminar ${row.title}`}
              >
                Eliminar PDF
              </button>
            </div>
          </li>
        ))}
      </ul>
      <p>{exports.items.length} PDFs cargados</p>
      <button
        type="button"
        disabled={exports.loading}
        onClick={exports.controller.refresh}
      >
        Actualizar PDFs
      </button>
      {exports.nextCursor && (
        <button
          type="button"
          disabled={exports.loading}
          onClick={exports.controller.loadMore}
        >
          Cargar más PDFs
        </button>
      )}
      {exports.busyKey && (
        <button type="button" onClick={exports.controller.cancelPending}>
          Cancelar operación PDF
        </button>
      )}
    </ModalDialog>
  );
}
