import { Download, UploadCloud, X } from "lucide-react";

export function TransferModal({ error = "", isLoading = false, isOpen, onClearHistory, onClose, transfers = [] }) {
  if (!isOpen) return null;

  const visibleTransfers = transfers.slice(0, 6);
  const activeTransfer = visibleTransfers.find((transfer) => transfer.status === "RUNNING");

  return (
    <section className="transfer-modal" aria-label="Cargas y descargas">
      <button className="transfer-close" onClick={onClose} aria-label="Cerrar cargas" type="button">
        <X size={20} />
      </button>
      <h3>
        <UploadCloud size={22} />
        Cargas y descargas
      </h3>

      {isLoading && <p className="transfer-state">Cargando procesos...</p>}
      {error && <p className="transfer-state error">{error}</p>}
      {!isLoading && !visibleTransfers.length && <p className="transfer-state">No hay cargas o descargas recientes.</p>}

      {visibleTransfers.map((transfer) => {
        const Icon = transfer.direction === "DOWNLOAD" ? Download : UploadCloud;
        const isActive = transfer.transferId === activeTransfer?.transferId;

        return (
          <div className={`transfer-row ${isActive ? "active" : ""}`.trim()} key={transfer.transferId}>
            <div className="transfer-item">
              <Icon size={18} />
              <div>
                <strong>{transfer.filename}</strong>
                <span>
                  {formatBytes(transfer.sizeBytes)} - {formatStatus(transfer.status)}
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

      <button className="transfer-clear" onClick={onClearHistory} type="button" disabled={!visibleTransfers.length}>
        Limpiar historico de procesos
      </button>
    </section>
  );
}

function formatStatus(status) {
  const labels = {
    PENDING: "Pendiente",
    RUNNING: "En proceso",
    COMPLETED: "Completado",
    FAILED: "Fallido",
    CANCELLED: "Cancelado",
  };
  return labels[status] || status;
}

function formatBytes(value) {
  if (!value) return "Tamano no disponible";
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}
