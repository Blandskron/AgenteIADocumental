import type { DocumentPreview } from "@/entities/document/model/types.ts";
import { ModalDialog } from "@/shared/components/ModalDialog.tsx";
import { Download, X } from "lucide-react";

export function DocumentPreviewModal({
  preview,
  onClose,
  onDownload,
}: {
  preview: DocumentPreview | null;
  onClose: () => void;
  onDownload: () => void;
}) {
  if (!preview) return null;

  const isPdf = preview.contentType.includes("pdf");
  const canEmbed = isPdf || preview.contentType.startsWith("image/");
  const embedSrc =
    isPdf && preview.page && preview.page > 0
      ? `${preview.url.split("#")[0]}#page=${preview.page}`
      : preview.url;

  return (
    <div className="document-preview-backdrop" role="presentation">
      <ModalDialog
        className="document-preview-modal"
        aria-label="Vista previa"
        onClose={onClose}
      >
        <header className="document-preview-header">
          <div>
            <p>
              Vista previa
              {preview.page ? ` · Página ${preview.page}` : ""}
              {preview.section ? ` · ${preview.section}` : ""}
            </p>
            <h3>{preview.filename}</h3>
          </div>
          <div className="document-preview-actions">
            <button
              className="icon-action-button"
              onClick={onDownload}
              aria-label="Descargar documento"
            >
              <Download size={18} />
            </button>
            <button
              className="icon-action-button"
              onClick={onClose}
              aria-label="Cerrar vista previa"
            >
              <X size={18} />
            </button>
          </div>
        </header>

        {preview.highlightText ? (
          <aside
            className="document-preview-citation"
            aria-label="Fragmento citado"
          >
            <strong>Fragmento citado:</strong> {preview.highlightText}
          </aside>
        ) : null}

        {canEmbed ? (
          <iframe
            sandbox=""
            className="document-preview-frame"
            src={embedSrc}
            title={preview.filename}
          />
        ) : (
          <div className="document-preview-empty">
            Este formato no se puede previsualizar directamente. Puedes
            descargarlo para abrirlo localmente.
          </div>
        )}
      </ModalDialog>
    </div>
  );
}
