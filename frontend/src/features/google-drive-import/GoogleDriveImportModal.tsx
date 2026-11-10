import { Cloud, X } from "lucide-react";
import { useEffect, useRef } from "react";
import { ImportAttemptNotice } from "./ImportAttemptNotice.tsx";
import type { DriveImportViewProps } from "./ui-types.ts";
export function GoogleDriveImportModal({
  history,
  onCancel,
  error,
  connection,
  fileIds,
  isBusy,
  isOpen,
  pickerConfigured,
  selectedFiles = [],
  onClose,
  onConnect,
  onDisconnect,
  operationScope,
  onFileIdsChange,
  onImport,
  onOpenPicker,
}: DriveImportViewProps & {
  error: string;
  isOpen: boolean;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (!isOpen) return;
    const element = dialog.current,
      opener = document.activeElement;
    element?.showModal();
    return () => {
      element?.close();
      if (opener instanceof HTMLElement && opener.isConnected) opener.focus();
    };
  }, [isOpen]);
  if (!isOpen) return null;

  return (
    <div className="move-document-backdrop" role="presentation">
      <dialog
        ref={dialog}
        onCancel={(event) => {
          event.preventDefault();
          onClose();
        }}
        className="move-document-modal google-drive-import-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="google-drive-import-title"
        onClick={(event) => event.stopPropagation()}
      >
        <header>
          <div>
            <p>Importar archivos</p>
            <h3 id="google-drive-import-title">Google Drive</h3>
          </div>
          <button
            className="icon-action-button"
            type="button"
            onClick={onClose}
            aria-label="Cerrar"
          >
            <X size={17} />
          </button>
        </header>
        <form className="google-drive-import-form" onSubmit={onImport}>
          {error && <p role="alert">{error}</p>}
          {history}
          {isBusy && (
            <button type="button" onClick={onCancel}>
              Dejar de esperar
            </button>
          )}
          <ImportAttemptNotice
            scope={operationScope}
            isBusy={isBusy}
            onRetry={onImport}
          />
          {!connection?.enabled && (
            <p role="status">La integración Google Drive está deshabilitada.</p>
          )}
          {connection?.grantStatus === "LEGACY" && (
            <p role="status">
              La conexión anterior requiere revisión de cifrado o una nueva
              autorización.
            </p>
          )}
          {connection?.grantStatus === "REAUTH_REQUIRED" && (
            <p role="status">
              Autoriza Google Drive nuevamente para continuar.
            </p>
          )}
          {connection?.grantStatus === "REVOKE_PENDING" && (
            <p role="status">
              Desconexión pendiente de confirmar con Google. Puedes
              reintentarla.
            </p>
          )}
          {(connection.version || 0) > 0 &&
            connection?.grantStatus !== "DISCONNECTED" && (
              <button
                type="button"
                className="action-button-secondary"
                disabled={isBusy || connection.busy}
                onClick={onDisconnect}
              >
                {connection.grantStatus === "REVOKE_PENDING"
                  ? "Reintentar desconexión"
                  : "Desconectar Google Drive"}
              </button>
            )}
          <div
            className={`google-drive-status ${connection?.connected ? "connected" : ""}`}
          >
            <Cloud size={18} />
            <span>
              {connection?.connected
                ? `Conectado${connection.providerAccountEmail ? ` como ${connection.providerAccountEmail}` : ""}`
                : "Conecta Google Drive para importar archivos seleccionados."}
            </span>
          </div>
          {!connection?.connected && (
            <button
              className="action-button-primary"
              type="button"
              disabled={
                isBusy ||
                !connection?.enabled ||
                connection?.grantStatus === "REVOKE_PENDING"
              }
              onClick={onConnect}
            >
              <Cloud size={16} /> Conectar Google Drive
            </button>
          )}
          {connection?.connected && (
            <>
              <button
                className="action-button-primary"
                type="button"
                onClick={onOpenPicker}
                disabled={
                  !connection?.enabled ||
                  connection.busy ||
                  !pickerConfigured ||
                  isBusy
                }
              >
                <Cloud size={16} /> Abrir selector de Drive
              </button>
              {!pickerConfigured && (
                <p className="google-drive-help">
                  Falta VITE_GOOGLE_PICKER_API_KEY para abrir el selector visual
                  de Google Drive.
                </p>
              )}
              {selectedFiles.length > 0 && (
                <div className="google-drive-picked-files">
                  {selectedFiles.map((file) => (
                    <span key={file.fileId}>{file.name || file.fileId}</span>
                  ))}
                </div>
              )}
              <label>
                IDs de archivos de Google Drive
                <textarea
                  disabled={isBusy}
                  maxLength={3300}
                  value={fileIds}
                  onChange={(event) => onFileIdsChange(event.target.value)}
                  placeholder="El selector completara este campo. Tambien puedes pegar fileId separados por coma o salto de linea."
                  rows={5}
                />
              </label>
              <footer>
                <button type="button" onClick={onClose}>
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={
                    !connection?.enabled ||
                    connection.busy ||
                    isBusy ||
                    !fileIds.trim()
                  }
                >
                  {isBusy ? "Importando..." : "Importar"}
                </button>
              </footer>
            </>
          )}
        </form>
      </dialog>
    </div>
  );
}
