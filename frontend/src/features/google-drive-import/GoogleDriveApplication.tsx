import { ChevronRight, Cloud, ShieldCheck, X } from "lucide-react";
import { ImportAttemptNotice } from "./ImportAttemptNotice.tsx";
import type { DriveImportViewProps } from "./ui-types.ts";
export function GoogleDriveApplication({
  history,
  onCancel,
  connection,
  fileIds,
  isBusy,
  pickerConfigured,
  selectedFiles,
  status,
  onBack,
  onConnect,
  onDisconnect,
  operationScope,
  onFileIdsChange,
  onImport,
  onOpenPicker,
  onRemoveSelectedFile,
}: DriveImportViewProps & {
  status: { error: string; success: string };
  onBack: () => void;
  onRemoveSelectedFile: (fileId: string) => void;
}) {
  return (
    <section className="applications-content application-detail">
      <nav className="application-breadcrumb" aria-label="Ruta">
        <button type="button" onClick={onBack}>
          Aplicaciones
        </button>
        <ChevronRight size={15} />
        <span>Google Drive</span>
      </nav>

      <div className="application-detail-hero">
        <ApplicationIcon />
        <div>
          <h1>Google Drive</h1>
          <p>
            Trabaja con documentos de Google Drive, incluidos Google Docs,
            Sheets, Slides, PDF, texto y DOCX. Sheets y Slides se convierten a
            PDF; XLSX y PPTX no se admiten.
          </p>
        </div>
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
          {connection?.connected ? "Reconectar" : "Conectar"}
        </button>
      </div>

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
        <p role="status">Autoriza Google Drive nuevamente para continuar.</p>
      )}
      {connection?.grantStatus === "REVOKE_PENDING" && (
        <p role="status">
          Desconexión pendiente de confirmar con Google. Puedes reintentarla.
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
        <ShieldCheck size={18} />
        <span>
          {connection?.connected
            ? `Conectado${connection.providerAccountEmail ? ` como ${connection.providerAccountEmail}` : ""}`
            : "Conecta Google Drive para importar archivos seleccionados."}
        </span>
      </div>

      <section className="application-info-panel">
        <h2>Informacion</h2>
        <dl>
          <div>
            <dt>Categoria</dt>
            <dd>Documentos</dd>
          </div>
          <div>
            <dt>Funcionalidades</dt>
            <dd>Busqueda de archivos, seleccion e importacion documental</dd>
          </div>
          <div>
            <dt>Uso</dt>
            <dd>
              Traer archivos externos para consultar, organizar y exportar en
              Blandskron Documental
            </dd>
          </div>
        </dl>
      </section>

      {connection?.connected && (
        <form className="application-import-panel" onSubmit={onImport}>
          <div>
            <h2>Importar documentos</h2>
            <p>Usa el selector visual o pega IDs de archivos de Drive.</p>
          </div>
          <button
            className="action-button-secondary"
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
              Falta VITE_GOOGLE_PICKER_API_KEY o VITE_GOOGLE_CLIENT_ID para
              abrir el selector visual.
            </p>
          )}
          {selectedFiles.length > 0 && (
            <div className="google-drive-picked-files">
              {selectedFiles.map((file) => (
                <span key={file.fileId}>
                  {file.name || file.fileId}
                  <button
                    type="button"
                    disabled={isBusy}
                    onClick={() => onRemoveSelectedFile(file.fileId)}
                    aria-label="Quitar archivo"
                  >
                    <X size={13} />
                  </button>
                </span>
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
              placeholder="Pega fileId separados por coma o salto de linea."
              rows={5}
            />
          </label>
          <button
            className="action-button-primary"
            type="submit"
            disabled={
              !connection?.enabled ||
              connection.busy ||
              isBusy ||
              !fileIds.trim()
            }
          >
            {isBusy ? "Importando..." : "Importar a Blandskron Documental"}
          </button>
        </form>
      )}

      {(status.error || status.success) && (
        <p
          role={status.error ? "alert" : "status"}
          className={`application-status ${status.error ? "error" : "success"}`}
        >
          {status.error || status.success}
        </p>
      )}
    </section>
  );
}

export function ApplicationIcon() {
  return (
    <span className="application-icon google-drive-icon" aria-hidden="true">
      <Cloud size={24} />
    </span>
  );
}
