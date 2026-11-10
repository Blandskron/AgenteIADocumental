import type { Transfer } from "@/features/transfers/api/transfers.api.ts";
import { Download, UploadCloud, X } from "lucide-react";
import { ModalDialog } from "../ModalDialog.tsx";
interface TransferModalProps {
  error?: string;
  isLoading?: boolean;
  isClearing?: boolean;
  hasMore?: boolean;
  onLoadMore: () => void;
  onRefresh: () => void;
  isOpen: boolean;
  onClearHistory: () => void;
  onClose: () => void;
  transfers?: Transfer[];
}

export function TransferModal({
  error = "",
  isLoading = false,
  isClearing = false,
  hasMore = false,
  onLoadMore,
  onRefresh,
  isOpen,
  onClearHistory,
  onClose,
  transfers = [],
}: TransferModalProps) {
  if (!isOpen) return null;

  const visibleTransfers = transfers;

  return (
    <ModalDialog
      className="transfer-modal"
      aria-label="Cargas y descargas"
      onClose={onClose}
    >
      <button
        className="transfer-close"
        onClick={onClose}
        aria-label="Cerrar cargas"
        type="button"
      >
        <X size={20} />
      </button>
      <h3>
        <UploadCloud size={22} />
        Cargas y descargas
      </h3>

      {isLoading && <p className="transfer-state">Cargando procesos...</p>}
      {error && <p className="transfer-state error">{error}</p>}
      {!isLoading && !visibleTransfers.length && (
        <p className="transfer-state">No hay cargas o descargas recientes.</p>
      )}

      {visibleTransfers.map((transfer) => {
        const Icon = transfer.direction === "DOWNLOAD" ? Download : UploadCloud;
        const isActive = transfer.status === "RUNNING";

        return (
          <div
            className={`transfer-row ${isActive ? "active" : ""}`.trim()}
            key={transfer.transferId}
          >
            <div className="transfer-item">
              <Icon size={18} />
              <div>
                <strong>{transfer.filename}</strong>
                <span>
                  {formatBytes(transfer.sizeBytes)} -{" "}
                  {formatStatus(transfer.status)}
                </span>
              </div>
              <b>{transfer.progress}%</b>
            </div>
            {isActive && (
              <div className="transfer-progress">
                <span style={{ width: `${transfer.progress}%` }} />
              </div>
            )}
          </div>
        );
      })}

      <p className="transfer-state">
        Cada limpieza elimina hasta 1000 procesos terminados y conserva los
        activos.
      </p>
      <p className="transfer-state">{transfers.length} procesos cargados</p>
      <button
        onClick={onRefresh}
        type="button"
        disabled={isLoading || isClearing}
      >
        Actualizar historial
      </button>
      {hasMore && (
        <button
          onClick={onLoadMore}
          type="button"
          disabled={isLoading || isClearing}
        >
          Cargar más procesos
        </button>
      )}
      <button
        className="transfer-clear"
        onClick={onClearHistory}
        type="button"
        disabled={isClearing || !visibleTransfers.length}
      >
        Limpiar procesos terminados
      </button>
    </ModalDialog>
  );
}

function formatStatus(status: string) {
  const labels: Record<string, string> = {
    PENDING: "Pendiente",
    RUNNING: "En proceso",
    COMPLETED: "Completado",
    FAILED: "Fallido",
    CANCELLED: "Cancelado",
  };
  return labels[status] || status;
}

function formatBytes(value: number | null) {
  if (value == null) return "Tamaño no disponible";
  if (value === 0) return "0 B";
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}
