import { getImportWarning } from "../../features/google-drive-import/import-result.js";
import { ImportAttemptNotice } from "../../features/google-drive-import/ImportAttemptNotice.jsx";
import { prepareImportAttempt, finishImportAttempt, rejectImportAttempt } from "../../features/google-drive-import/import-attempt.js";
import { useEffect, useRef, useState } from "react";
import { ChevronRight, Cloud, ShieldCheck, X } from "lucide-react";

import { env } from "../../app/config/env";
import { appRoutes } from "../../app/router/routes";
import { useAuthContext } from "../../app/providers/AuthProvider";
import { AppShell } from "../../shared/layouts/AppShell";
import { Sidebar } from "../../widgets/Sidebar/Sidebar";
import { useConversations } from "../../features/conversations/hooks/useConversations";
import {
  importGoogleDriveFiles,
} from "../../features/google-drive-import/api/google-drive-import.api";
import { useDriveConnection } from "../../features/google-drive-import/useDriveConnection.js";
import { openGoogleDrivePicker } from "../../features/google-drive-import/google-picker";

export function ApplicationsPage({ activeView = appRoutes.applications, onNavigate }) {
  const {
    conversationClient,
    currentUser,
    googleDriveImportClient,
    profileSessionKey,
    logout,
    storageScope,
  } = useAuthContext();
  const {
    activeConversation,
    conversations,
    createNewConversation,
    deleteConversation,
    setActiveId,
  } = useConversations(storageScope, conversationClient);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const drive = useDriveConnection(googleDriveImportClient, profileSessionKey);
  const connection = drive.connection;
  const [fileIds, setFileIds] = useState("");
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [isBusy, setIsBusy] = useState(false);
  const [status, setStatus] = useState({ error: "", success: "" });
  const importBusyRef = useRef(false);
  const importEpoch = useRef(0);
  const driveClientRef = useRef(googleDriveImportClient);
  driveClientRef.current = { client: googleDriveImportClient, version: connection.version, connected: connection.connected, busy: drive.busy };
  useEffect(() => {
    importEpoch.current++;
    importBusyRef.current = false;
    setIsBusy(false);
    setSelectedFiles([]);
    setFileIds("");
  }, [googleDriveImportClient, connection.providerAccountId]);
  const isDriveDetail = activeView === appRoutes.googleDriveApplication;


  const handleConnectDrive = drive.connect;

  async function handleOpenGooglePicker() {
    setStatus({ error: "", success: "" });
    try {
      const pickerContext = driveClientRef.current;
      const pickedFiles = await openGoogleDrivePicker({
        connection,
        appId: env.googlePickerAppId,
        clientId: env.googleClientId,
        developerKey: env.googlePickerApiKey,
      });
      const current = driveClientRef.current;
      if (current.client !== pickerContext.client || current.version !== pickerContext.version || !current.connected || current.busy || !pickedFiles.length) return;
      setSelectedFiles(pickedFiles);
      setFileIds(pickedFiles.map((file) => file.fileId).join("\n"));
    } catch (error) {
      setStatus({ error: error.message, success: "" });
    }
  }

  async function handleImportDriveFiles(event, previousInput = null) {
    event.preventDefault();
    const files = previousInput?.files || (selectedFiles.length
      ? selectedFiles
      : fileIds
          .split(/[\n,]/)
          .map((value) => value.trim())
          .filter(Boolean)
          .map((fileId) => ({ fileId })));

    if (!files.length || importBusyRef.current) return;
    importBusyRef.current = true;
    const generation = ++importEpoch.current;

    setIsBusy(true);
    setStatus({ error: "", success: "" });
    let attempt;
    try {
      const input = previousInput || { files, metadata: { imported_from_applications: true } };
      attempt = prepareImportAttempt(profileSessionKey, input, connection.version);
      const imported = await importGoogleDriveFiles(googleDriveImportClient, { ...input, ...attempt });
      if (importEpoch.current !== generation) return;
      finishImportAttempt(profileSessionKey, attempt.operationId, imported);
      if (imported.status === "REVIEW_REQUIRED") {
        setStatus({ error: "La carga tiene un resultado incierto. Revisa el historial antes de reintentar.", success: "" });
        return;
      }
      if (!previousInput) setFileIds("");
      if (!previousInput) setSelectedFiles([]);
      const warning = getImportWarning(imported);
      setStatus({ error: warning, success: warning ? "" : "Documentos enviados a procesamiento." });
    } catch (error) {
      if (importEpoch.current !== generation) return;
      if (attempt) rejectImportAttempt(profileSessionKey, attempt.operationId, error);
      if (error.payload?.code === "import_connection_changed") await drive.refresh();
      setStatus({ error: error.message, success: "" });
    } finally {
      if (importEpoch.current === generation) importBusyRef.current = false;
      if (importEpoch.current === generation) setIsBusy(false);
    }
  }

  return (
    <AppShell
      sidebarOpen={sidebarOpen}
      sidebar={
        <Sidebar
          activeConversation={activeConversation}
          activeRoute={appRoutes.applications}
          collapsed={!sidebarOpen}
          conversations={conversations}
          onClose={() => setSidebarOpen(false)}
          onCreateConversation={createNewConversation}
          onDeleteConversation={deleteConversation}
          onLogout={logout}
          onNavigate={onNavigate}
          onOpen={() => setSidebarOpen(true)}
          onSelectConversation={setActiveId}
          user={currentUser}
        />
      }
    >
      <main className="applications-page blandskron-screen">
        {isDriveDetail ? (
          <GoogleDriveApplication
            operationScope={profileSessionKey}
            connection={connection}
            fileIds={fileIds}
            isBusy={isBusy || drive.busy}
            pickerConfigured={Boolean(env.googlePickerApiKey && env.googleClientId)}
            selectedFiles={selectedFiles}
            status={{ ...status, error: drive.error || status.error }}
            onBack={() => onNavigate?.(appRoutes.applications)}
            onConnect={handleConnectDrive}
            onDisconnect={drive.disconnect}
            onFileIdsChange={setFileIds}
            onImport={handleImportDriveFiles}
            onOpenPicker={handleOpenGooglePicker}
            onRemoveSelectedFile={(fileId) => {
              const nextFiles = selectedFiles.filter((file) => file.fileId !== fileId);
              setSelectedFiles(nextFiles);
              setFileIds(nextFiles.map((file) => file.fileId).join("\n"));
            }}
          />
        ) : (
          <ApplicationsList onNavigate={onNavigate} />
        )}
      </main>
    </AppShell>
  );
}

function ApplicationsList({ onNavigate }) {
  return (
    <section className="applications-content">
      <div className="applications-heading">
        <h1>Aplicaciones</h1>
        <p>Conecta fuentes externas para traer documentos a Blandskron Documental.</p>
      </div>

      <div className="applications-grid">
        <button className="application-row" onClick={() => onNavigate?.(appRoutes.googleDriveApplication)} type="button">
          <ApplicationIcon />
          <span>
            <strong>Google Drive</strong>
            <small>Importa archivos a tu biblioteca documental con una cuenta de Google configurada.</small>
          </span>
          <ChevronRight size={18} />
        </button>
      </div>
    </section>
  );
}

function GoogleDriveApplication({
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
}) {
  return (
    <section className="applications-content application-detail">
      <nav className="application-breadcrumb" aria-label="Ruta">
        <button type="button" onClick={onBack}>Aplicaciones</button>
        <ChevronRight size={15} />
        <span>Google Drive</span>
      </nav>

      <div className="application-detail-hero">
        <ApplicationIcon />
        <div>
          <h1>Google Drive</h1>
          <p>
            Trabaja con documentos de Google Drive, incluidos Google Docs, Sheets, Slides,
            archivos de Excel, PDF y archivos cargados, para incorporarlos a tu proyecto documental.
          </p>
        </div>
        <button className="action-button-primary" type="button" disabled={isBusy || !connection?.enabled || connection?.grantStatus === "REVOKE_PENDING"} onClick={onConnect}>
          {connection?.connected ? "Reconectar" : "Conectar"}
        </button>
      </div>

      <ImportAttemptNotice scope={operationScope} isBusy={isBusy} onRetry={onImport} />
      {!connection?.enabled && <p role="status">La integración Google Drive está deshabilitada.</p>}
      {connection?.grantStatus === "LEGACY" && <p role="status">La conexión anterior requiere revisión de cifrado o una nueva autorización.</p>}
      {connection?.grantStatus === "REAUTH_REQUIRED" && <p role="status">Autoriza Google Drive nuevamente para continuar.</p>}
      {connection?.grantStatus === "REVOKE_PENDING" && <p role="status">Desconexión pendiente de confirmar con Google. Puedes reintentarla.</p>}
      {(connection?.version > 0 && connection?.grantStatus !== "DISCONNECTED") && (
        <button type="button" className="action-button-secondary" disabled={isBusy || connection.busy} onClick={onDisconnect}>
          {connection.grantStatus === "REVOKE_PENDING" ? "Reintentar desconexión" : "Desconectar Google Drive"}
        </button>
      )}
      <div className={`google-drive-status ${connection?.connected ? "connected" : ""}`}>
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
            <dd>Traer archivos externos para consultar, organizar y exportar en Blandskron Documental</dd>
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
            disabled={!connection?.enabled || connection.busy || !pickerConfigured || isBusy}
          >
            <Cloud size={16} /> Abrir selector de Drive
          </button>
          {!pickerConfigured && (
            <p className="google-drive-help">
              Falta VITE_GOOGLE_PICKER_API_KEY o VITE_GOOGLE_CLIENT_ID para abrir el selector visual.
            </p>
          )}
          {selectedFiles.length > 0 && (
            <div className="google-drive-picked-files">
              {selectedFiles.map((file) => (
                <span key={file.fileId}>
                  {file.name || file.fileId}
                  <button type="button" onClick={() => onRemoveSelectedFile(file.fileId)} aria-label="Quitar archivo">
                    <X size={13} />
                  </button>
                </span>
              ))}
            </div>
          )}
          <label>
            IDs de archivos de Google Drive
            <textarea
              value={fileIds}
              onChange={(event) => onFileIdsChange(event.target.value)}
              placeholder="Pega fileId separados por coma o salto de linea."
              rows={5}
            />
          </label>
          <button className="action-button-primary" type="submit" disabled={!connection?.enabled || connection.busy || isBusy || !fileIds.trim()}>
            {isBusy ? "Importando..." : "Importar a Blandskron Documental"}
          </button>
        </form>
      )}

      {(status.error || status.success) && (
        <p className={`application-status ${status.error ? "error" : "success"}`}>
          {status.error || status.success}
        </p>
      )}
    </section>
  );
}

function ApplicationIcon() {
  return (
    <span className="application-icon google-drive-icon" aria-hidden="true">
      <Cloud size={24} />
    </span>
  );
}
