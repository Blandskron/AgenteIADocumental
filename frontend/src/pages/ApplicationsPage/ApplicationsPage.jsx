import { useEffect, useState } from "react";
import { ChevronRight, Cloud, ShieldCheck, X } from "lucide-react";

import { env } from "../../app/config/env";
import { appRoutes } from "../../app/router/routes";
import { useAuthContext } from "../../app/providers/AuthProvider";
import { AppShell } from "../../shared/layouts/AppShell";
import { Sidebar } from "../../widgets/Sidebar/Sidebar";
import { useConversations } from "../../features/conversations/hooks/useConversations";
import {
  connectGoogleDrive,
  getGoogleDriveAuthUrl,
  getGoogleDriveConnection,
  importGoogleDriveFiles,
} from "../../features/google-drive-import/api/google-drive-import.api";
import { openGoogleDrivePicker } from "../../features/google-drive-import/google-picker";
import googleDriveLogoUrl from "../../../logodrive.png";
import sharePointLogoUrl from "../../../logoSharepoint.png";

const APPLICATIONS = [
  {
    id: "google-drive",
    route: appRoutes.googleDriveApplication,
    name: "Google Drive",
    description: "Trae Google Docs, Sheets, Slides, Excel y PDF a tu biblioteca documental",
    enabled: true,
  },
  {
    id: "sharepoint",
    name: "SharePoint",
    description: "Proxima integracion para sitios compartidos y bibliotecas Microsoft",
    enabled: false,
  },
];

export function ApplicationsPage({ activeView = appRoutes.applications, onNavigate }) {
  const {
    conversationClient,
    currentUser,
    googleDriveImportClient,
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
  const [connection, setConnection] = useState({ connected: false });
  const [fileIds, setFileIds] = useState("");
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [isBusy, setIsBusy] = useState(false);
  const [status, setStatus] = useState({ error: "", success: "" });
  const isDriveDetail = activeView === appRoutes.googleDriveApplication;

  useEffect(() => {
    if (!googleDriveImportClient) return;

    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");

    if (code) {
      connectGoogleDrive(googleDriveImportClient, code)
        .then((nextConnection) => {
          setConnection(nextConnection);
          setStatus({ error: "", success: "Google Drive conectado correctamente." });
          window.history.replaceState({}, document.title, appRoutes.googleDriveApplication);
        })
        .catch((error) => setStatus({ error: error.message, success: "" }));
      return;
    }

    getGoogleDriveConnection(googleDriveImportClient)
      .then(setConnection)
      .catch(() => {});
  }, [googleDriveImportClient]);

  async function handleConnectDrive() {
    setStatus({ error: "", success: "" });
    try {
      const payload = await getGoogleDriveAuthUrl(googleDriveImportClient, window.location.href);
      window.location.assign(payload.authorization_url);
    } catch (error) {
      setStatus({ error: error.message, success: "" });
    }
  }

  async function handleOpenGooglePicker() {
    setStatus({ error: "", success: "" });
    try {
      const pickedFiles = await openGoogleDrivePicker({
        appId: env.googlePickerAppId,
        clientId: env.googleClientId,
        developerKey: env.googlePickerApiKey,
      });
      if (!pickedFiles.length) return;
      setSelectedFiles(pickedFiles);
      setFileIds(pickedFiles.map((file) => file.fileId).join("\n"));
    } catch (error) {
      setStatus({ error: error.message, success: "" });
    }
  }

  async function handleImportDriveFiles(event) {
    event.preventDefault();
    const files = selectedFiles.length
      ? selectedFiles
      : fileIds
          .split(/[\n,]/)
          .map((value) => value.trim())
          .filter(Boolean)
          .map((fileId) => ({ fileId }));

    if (!files.length) return;

    setIsBusy(true);
    setStatus({ error: "", success: "" });
    try {
      await importGoogleDriveFiles(googleDriveImportClient, {
        files,
        metadata: { imported_from_applications: true },
      });
      setFileIds("");
      setSelectedFiles([]);
      setStatus({ error: "", success: "Documentos enviados a procesamiento." });
    } catch (error) {
      setStatus({ error: error.message, success: "" });
    } finally {
      setIsBusy(false);
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
            connection={connection}
            fileIds={fileIds}
            isBusy={isBusy}
            pickerConfigured={Boolean(env.googlePickerApiKey && env.googleClientId)}
            selectedFiles={selectedFiles}
            status={status}
            onBack={() => onNavigate?.(appRoutes.applications)}
            onConnect={handleConnectDrive}
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
        {APPLICATIONS.map((application) => (
          <button
            className={`application-row ${!application.enabled ? "disabled" : ""}`}
            disabled={!application.enabled}
            aria-disabled={!application.enabled}
            key={application.id}
            onClick={() => application.route && onNavigate?.(application.route)}
            type="button"
          >
            <ApplicationIcon id={application.id} />
            <span>
              <strong>{application.name}</strong>
              <small>{application.description}</small>
            </span>
            {application.enabled ? <ChevronRight size={18} /> : <em>Pronto</em>}
          </button>
        ))}
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
        <ApplicationIcon id="google-drive" />
        <div>
          <h1>Google Drive</h1>
          <p>
            Trabaja con documentos de Google Drive, incluidos Google Docs, Sheets, Slides,
            archivos de Excel, PDF y archivos cargados, para incorporarlos a tu proyecto documental.
          </p>
        </div>
        <button className="action-button-primary" type="button" onClick={onConnect}>
          {connection?.connected ? "Reconectar" : "Conectar"}
        </button>
      </div>

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
            disabled={!pickerConfigured || isBusy}
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
          <button className="action-button-primary" type="submit" disabled={isBusy || !fileIds.trim()}>
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

function ApplicationIcon({ id }) {
  if (id === "google-drive") {
    return (
      <span className="application-icon google-drive-icon" aria-hidden="true">
        <img src={googleDriveLogoUrl} alt="" />
      </span>
    );
  }

  return (
    <span className="application-icon sharepoint-icon" aria-hidden="true">
      <img src={sharePointLogoUrl} alt="" />
    </span>
  );
}
