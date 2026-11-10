import type { PageProps } from "@/app/router/useAppRouter.ts";
import { DriveHistory } from "@/features/google-drive-import/DriveHistory.tsx";
import {
  ApplicationIcon,
  GoogleDriveApplication,
} from "@/features/google-drive-import/GoogleDriveApplication.tsx";
import type {
  DriveFile,
  DriveInput,
} from "@/features/google-drive-import/types.ts";
import type { ImportEvent } from "@/features/google-drive-import/ui-types.ts";
import { useDriveImport } from "@/features/google-drive-import/useDriveImport.ts";
import { useSidebarState } from "@/shared/hooks/useSidebarState.ts";
import { ChevronRight } from "lucide-react";
import { useEffect, useState } from "react";

import { env } from "@/app/config/env.ts";
import { useAuthContext } from "@/app/providers/AuthProvider.tsx";
import { appRoutes } from "@/app/router/routes.ts";
import { useConversations } from "@/features/conversations/hooks/useConversations.ts";
import { openGoogleDrivePicker } from "@/features/google-drive-import/google-picker.ts";
import { useDriveConnection } from "@/features/google-drive-import/useDriveConnection.ts";
import { AppShell } from "@/shared/layouts/AppShell.tsx";
import { Sidebar } from "@/widgets/Sidebar/Sidebar.tsx";

export function ApplicationsPage({
  activeView = appRoutes.applications,
  onNavigate,
}: PageProps & { activeView?: string }) {
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
  const [sidebarOpen, setSidebarOpen] = useSidebarState();
  const drive = useDriveConnection(googleDriveImportClient, profileSessionKey);
  const connection = drive.connection;
  const [fileIds, setFileIds] = useState("");
  const [selectedFiles, setSelectedFiles] = useState<DriveFile[]>([]);
  const importing = useDriveImport(
    googleDriveImportClient,
    profileSessionKey,
    connection,
    drive.busy,
  );
  const isBusy = importing.busy;
  const status = importing;
  useEffect(() => {
    setSelectedFiles([]);
    setFileIds("");
  }, [googleDriveImportClient, connection.providerAccountId]);
  const isDriveDetail = activeView === appRoutes.googleDriveApplication;

  const handleConnectDrive = drive.connect;

  function handleOpenGooglePicker() {
    return importing.controller.picker(
      (signal) =>
        openGoogleDrivePicker({
          connection,
          signal,
          appId: env.googlePickerAppId,
          clientId: env.googleClientId,
          developerKey: env.googlePickerApiKey,
        }),
      (files) => {
        setSelectedFiles(files);
        setFileIds(files.map((file) => file.fileId).join("\n"));
      },
    );
  }
  function handleImportDriveFiles(
    event: ImportEvent,
    previousInput: DriveInput | null = null,
  ) {
    event.preventDefault();
    const files = selectedFiles.length
      ? selectedFiles
      : fileIds
          .split(/[\n,]/)
          .map((v) => v.trim())
          .filter(Boolean)
          .map((fileId) => ({ fileId }));
    return importing.controller.import(
      previousInput || {
        files,
        metadata: { imported_from_applications: true },
      },
      connection.version,
      () => {
        if (!previousInput) {
          setFileIds("");
          setSelectedFiles([]);
        }
      },
      drive.refresh,
    );
  }

  return (
    <AppShell
      sidebarOpen={sidebarOpen}
      onSidebarChange={setSidebarOpen}
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
      <main
        id="main-content"
        tabIndex={-1}
        className="applications-page blandskron-screen"
      >
        {isDriveDetail ? (
          <GoogleDriveApplication
            history={
              <DriveHistory
                client={googleDriveImportClient}
                scope={profileSessionKey}
              />
            }
            onCancel={() => importing.controller.cancel()}
            operationScope={profileSessionKey}
            connection={connection}
            fileIds={fileIds}
            isBusy={isBusy || drive.busy}
            pickerConfigured={Boolean(
              env.googlePickerApiKey && env.googleClientId,
            )}
            selectedFiles={selectedFiles}
            status={{ ...status, error: drive.error || status.error }}
            onBack={() => onNavigate?.(appRoutes.applications)}
            onConnect={handleConnectDrive}
            onDisconnect={drive.disconnect}
            onFileIdsChange={(value) => {
              setFileIds(value);
              setSelectedFiles([]);
            }}
            onImport={handleImportDriveFiles}
            onOpenPicker={handleOpenGooglePicker}
            onRemoveSelectedFile={(fileId) => {
              const nextFiles = selectedFiles.filter(
                (file) => file.fileId !== fileId,
              );
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

function ApplicationsList({ onNavigate }: PageProps) {
  return (
    <section className="applications-content">
      <div className="applications-heading">
        <h1>Aplicaciones</h1>
        <p>
          Conecta fuentes externas para traer documentos a Blandskron
          Documental.
        </p>
      </div>

      <div className="applications-grid">
        <button
          className="application-row"
          onClick={() => onNavigate?.(appRoutes.googleDriveApplication)}
          type="button"
        >
          <ApplicationIcon />
          <span>
            <strong>Google Drive</strong>
            <small>
              Importa archivos a tu biblioteca documental con una cuenta de
              Google configurada.
            </small>
          </span>
          <ChevronRight size={18} />
        </button>
      </div>
    </section>
  );
}
