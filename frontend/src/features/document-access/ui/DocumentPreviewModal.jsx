import { Download, X } from "lucide-react";
import { ModalDialog } from "../../../shared/components/ModalDialog";

export function DocumentPreviewModal({ preview, onClose, onDownload }) {
  if (!preview) return null;

  const canEmbed = preview.contentType.includes("pdf") || preview.contentType.startsWith("image/");

  return (
    <div className="document-preview-backdrop" role="presentation">
      <ModalDialog className="document-preview-modal" aria-label="Vista previa" onClose={onClose}>
        <header className="document-preview-header">
          <div>
            <p>Vista previa</p>
            <h3>{preview.filename}</h3>
          </div>
          <div className="document-preview-actions">
            <button className="icon-action-button" onClick={onDownload} aria-label="Descargar documento">
              <Download size={18} />
            </button>
            <button className="icon-action-button" onClick={onClose} aria-label="Cerrar vista previa">
              <X size={18} />
            </button>
          </div>
        </header>

        {canEmbed ? (
          <iframe className="document-preview-frame" src={preview.url} title={preview.filename} />
        ) : (
          <div className="document-preview-empty">
            Este formato no se puede previsualizar directamente. Puedes descargarlo para abrirlo localmente.
          </div>
        )}
      </ModalDialog>
    </div>
  );
}
