import type { PageProps } from "@/app/router/useAppRouter.ts";
import type {
  DocumentItem,
  DocumentPreview,
  Folder as FolderItem,
} from "@/entities/document/model/types.ts";
import type {
  Assignment,
  Notification,
} from "@/features/document-access/api/document-access.api.ts";
import {
  AssignDocumentModal,
  AssignmentWorkflowList,
  WorkflowPagination,
} from "@/features/document-access/ui/AssignmentWorkflow.tsx";
import { CreateFolderDialog } from "@/features/document-library/ui/CreateFolderDialog.tsx";
import {
  MoveDocumentModal,
  formatFolderCount,
} from "@/features/document-library/ui/MoveDocumentModal.tsx";
import { DriveHistory } from "@/features/google-drive-import/DriveHistory.tsx";
import { GoogleDriveImportModal } from "@/features/google-drive-import/GoogleDriveImportModal.tsx";
import type {
  DriveFile,
  DriveInput,
} from "@/features/google-drive-import/types.ts";
import type { ImportEvent } from "@/features/google-drive-import/ui-types.ts";
import { useDriveImport } from "@/features/google-drive-import/useDriveImport.ts";
import { useSidebarState } from "@/shared/hooks/useSidebarState.ts";
import { toError } from "@/shared/lib/errors.ts";
import { formatDate } from "@/shared/utils/format.ts";
import {
  Bell,
  Check,
  Cloud,
  FileText,
  Folder,
  LayoutGrid,
  List,
  Plus,
  Send,
  Star,
  Upload,
  X,
} from "lucide-react";
import type { ChangeEvent, FormEvent } from "react";
import { useEffect, useRef, useState } from "react";

import { env } from "@/app/config/env.ts";
import { useAuthContext } from "@/app/providers/AuthProvider.tsx";
import { appRoutes } from "@/app/router/routes.ts";
import { useConversations } from "@/features/conversations/hooks/useConversations.ts";
import {
  acceptAssignment,
  assignDocument,
  cancelAssignment,
  deleteDocument,
  downloadDocument,
  getDocumentPreview,
  listAssignedToMe,
  listManagedByMe,
  listNotifications,
  markNotificationRead,
  rejectAssignment,
  signAssignment,
} from "@/features/document-access/api/document-access.api";
import { useWorkflowList } from "@/features/document-access/hooks/useWorkflowList.ts";
import { DocumentPreviewModal } from "@/features/document-access/ui/DocumentPreviewModal.tsx";
import { useDocumentLibrary } from "@/features/document-library/hooks/useDocumentLibrary.ts";
import { buildChatSelection } from "@/features/document-search/api/document-search.api";
import { useDocumentSearch } from "@/features/document-search/hooks/useDocumentSearch.ts";
import { DocumentResultCard } from "@/features/document-search/ui/DocumentResultCard.tsx";
import { DocumentSearchBar } from "@/features/document-search/ui/DocumentSearchBar.tsx";
import {
  runDocumentDownload,
  runDocumentUpload,
} from "@/features/transfers/document-transfer-flows.ts";
import { useTransfers } from "@/features/transfers/hooks/useTransfers.ts";
import { ConfirmModal } from "@/shared/components/ConfirmModal/ConfirmModal.tsx";
import { TransferModal } from "@/shared/components/TransferModal/TransferModal.tsx";
import { TransferWarning } from "@/shared/components/TransferModal/TransferWarning.tsx";
import { AppShell } from "@/shared/layouts/AppShell.tsx";
import { Sidebar } from "@/widgets/Sidebar/Sidebar.tsx";

// Nuevos importadores para gestión de carga y mapeo de carpetas
import {
  hasTenantPermission,
  isTenantAdmin,
} from "@/entities/auth/model/auth.user";
import { listUsers } from "@/features/auth/api/user-management.api";
import { LibraryPagination } from "@/features/document-library/ui/LibraryPagination.tsx";
import { waitForDocumentProcessed } from "@/features/documents/api/document-status.poller";
import { uploadDocument } from "@/features/documents/api/document.api";
import { isDocumentProcessed } from "@/features/documents/lib/document-status.ts";
import { openGoogleDrivePicker } from "@/features/google-drive-import/google-picker.ts";
import { useDriveConnection } from "@/features/google-drive-import/useDriveConnection.ts";

export function DocumentSearchPage({
  activeView = appRoutes.documents,
  onNavigate,
}: PageProps & { activeView?: string }) {
  const {
    conversationClient,
    currentUser,
    documentAccessClient,
    documentLibraryClient,
    documentSearchClient,
    documentTransferClient,
    documentClient,
    googleDriveImportClient,
    profileSessionKey,
    authClient,
    logout,
    storageScope,
  } = useAuthContext();
  const {
    activeConversation,
    addMessage,
    conversations,
    createNewConversation,
    deleteConversation,
    setActiveId,
    setSelectedDocuments,
  } = useConversations(storageScope, conversationClient);
  const search = useDocumentSearch(documentSearchClient);
  const library = useDocumentLibrary(documentLibraryClient, search.documents);
  const transfers = useTransfers(documentTransferClient);
  const [sidebarOpen, setSidebarOpen] = useSidebarState();
  const [preview, setPreview] = useState<
    (DocumentPreview & { document: DocumentItem }) | null
  >(null);
  const [actionError, setActionError] = useState("");
  const [transfersOpen, setTransfersOpen] = useState(false);
  const [deleteModal, setDeleteModal] = useState<{
    open: boolean;
    document: DocumentItem | null;
  }>({ open: false, document: null });
  const [moveModal, setMoveModal] = useState<{
    open: boolean;
    document: DocumentItem | null;
  }>({ open: false, document: null });
  const [createFolderModalOpen, setCreateFolderModalOpen] = useState(false);
  const [assignmentModal, setAssignmentModal] = useState<{
    open: boolean;
    document: DocumentItem | null;
  }>({ open: false, document: null });
  const [assignmentForm, setAssignmentForm] = useState({
    userId: "",
    allowDownload: true,
    dueAt: "",
  });
  const [tenantUsers, setTenantUsers] = useState<
    Awaited<ReturnType<typeof listUsers>>
  >([]);
  const assigned = useWorkflowList(documentAccessClient, listAssignedToMe);
  const managed = useWorkflowList(documentAccessClient, listManagedByMe);
  const notificationList = useWorkflowList(
    documentAccessClient,
    listNotifications,
  );
  const assignedDocuments = assigned.items;
  const managedDocuments = managed.items;
  const notifications = notificationList.items;
  const [viewMode, setViewMode] = useState("grid");
  const [showRecent, setShowRecent] = useState(false);
  const [driveModalOpen, setDriveModalOpen] = useState(false);
  const drive = useDriveConnection(googleDriveImportClient, profileSessionKey);
  const driveConnection = drive.connection;
  const [driveFileIds, setDriveFileIds] = useState("");
  const [selectedDriveFiles, setSelectedDriveFiles] = useState<DriveFile[]>([]);
  const importing = useDriveImport(
    googleDriveImportClient,
    profileSessionKey,
    driveConnection,
    drive.busy,
  );
  const driveImportBusy = importing.busy;
  useEffect(() => {
    setSelectedDriveFiles([]);
    setDriveFileIds("");
  }, [googleDriveImportClient, driveConnection.providerAccountId]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const canAssignDocuments =
    isTenantAdmin(currentUser) ||
    hasTenantPermission(currentUser, "assign_documents");
  const canUploadDocuments =
    isTenantAdmin(currentUser) ||
    hasTenantPermission(currentUser, "upload_documents");
  const canDownloadDocuments =
    isTenantAdmin(currentUser) ||
    hasTenantPermission(currentUser, "download_documents");
  const canManageDocuments =
    isTenantAdmin(currentUser) ||
    hasTenantPermission(currentUser, "manage_documents");

  useEffect(() => {
    function openTransfers() {
      setTransfersOpen(true);
    }

    window.addEventListener("blandskron:open-transfers", openTransfers);
    return () => {
      window.removeEventListener("blandskron:open-transfers", openTransfers);
      if (preview?.url) URL.revokeObjectURL(preview.url);
    };
  }, [preview?.url]);

  useEffect(() => {
    if (!canAssignDocuments) return;
    listUsers(authClient)
      .then(setTenantUsers)
      .catch(() => setTenantUsers([]));
  }, [authClient, canAssignDocuments]);

  const closeFolder = library.closeFolder;
  useEffect(() => {
    if (activeView !== appRoutes.documentFolders) {
      closeFolder();
    }
  }, [activeView, closeFolder]);

  const handleTriggerUpload = () => {
    if (!canUploadDocuments) {
      setActionError("No tienes permiso para subir documentos.");
      return;
    }
    fileInputRef.current?.click();
  };

  const handleOpenDriveModal = async () => {
    setDriveModalOpen(true);
    setActionError("");
    await drive.refresh();
  };

  const handleConnectDrive = drive.connect;

  const handleImportDriveFiles = (
    event: ImportEvent,
    previousInput: DriveInput | null = null,
  ) => {
    event.preventDefault();
    const files = selectedDriveFiles.length
      ? selectedDriveFiles
      : driveFileIds
          .split(/[\n,]/)
          .map((v) => v.trim())
          .filter(Boolean)
          .map((fileId) => ({ fileId }));
    return importing.controller.import(
      previousInput || {
        files,
        folderId: library.selectedFolder?.folderId || null,
        metadata: { imported_from_ui: true },
      },
      driveConnection.version,
      async (_result, current) => {
        if (!previousInput) {
          setDriveFileIds("");
          setSelectedDriveFiles([]);
        }
        setDriveModalOpen(false);
        await search.runSearch();
        if (current()) await library.refreshLibrary();
      },
      drive.refresh,
    );
  };
  const handleOpenGooglePicker = () =>
    importing.controller.picker(
      (signal) =>
        openGoogleDrivePicker({
          connection: driveConnection,
          signal,
          appId: env.googlePickerAppId,
          clientId: env.googleClientId,
          developerKey: env.googlePickerApiKey,
        }),
      (files) => {
        setSelectedDriveFiles(files);
        setDriveFileIds(files.map((file) => file.fileId).join("\n"));
      },
    );

  const handleUploadFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setActionError("");
    try {
      await runDocumentUpload({
        transfers,
        file,
        upload: () => uploadDocument(documentClient, { file }),
        poll: (id) => waitForDocumentProcessed(documentClient, id),
        isProcessed: isDocumentProcessed,
      });
      await search.runSearch();
      await library.refreshLibrary();
    } catch (caughtError) {
      const err = toError(caughtError);
      setActionError(err.message);
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  async function sendToChat(document: DocumentItem) {
    if (!activeConversation?.id) return;
    const selection = await buildChatSelection(documentSearchClient, {
      documentIds: [document.documentId],
      sessionId: activeConversation.id,
    });
    const message = `Documento seleccionado: ${document.filename}. Ya puedes pedirme que lo analice.`;
    setSelectedDocuments(selection.documents);
    if (
      !activeConversation.messages?.some((item) => item.content === message)
    ) {
      addMessage({ role: "assistant", content: message, sources: [] });
    }
    onNavigate?.(appRoutes.chat);
  }

  async function previewDocument(document: DocumentItem) {
    setActionError("");
    if (preview?.url) URL.revokeObjectURL(preview.url);
    try {
      setPreview({
        ...(await getDocumentPreview(documentAccessClient, document)),
        document,
      });
    } catch (caughtError) {
      const requestError = toError(caughtError);
      setActionError(requestError.message);
    }
  }

  async function downloadSelectedDocument(document: DocumentItem) {
    setActionError("");
    try {
      await runDocumentDownload({
        transfers,
        document,
        download: () => downloadDocument(documentAccessClient, document),
      });
    } catch (caughtError) {
      const requestError = toError(caughtError);
      setActionError(requestError.message);
    }
  }

  function openDeleteModal(document: DocumentItem) {
    setDeleteModal({ open: true, document });
  }

  function closeDeleteModal() {
    setDeleteModal({ open: false, document: null });
  }

  function openMoveModal(document: DocumentItem) {
    setMoveModal({ open: true, document });
  }

  function openAssignmentModal(document: DocumentItem) {
    setAssignmentModal({ open: true, document });
    setAssignmentForm({ userId: "", allowDownload: true, dueAt: "" });
  }

  function closeMoveModal() {
    setMoveModal({ open: false, document: null });
  }

  async function confirmDeleteDocument() {
    if (!deleteModal.document) return;
    setActionError("");
    try {
      await deleteDocument(
        documentAccessClient,
        deleteModal.document.documentId,
      );
      await search.runSearch();
      await library.refreshLibrary();
      closeDeleteModal();
    } catch (caughtError) {
      const requestError = toError(caughtError);
      setActionError(requestError.message);
    }
  }

  async function moveSelectedDocument(folderId: string | null = null) {
    if (!moveModal.document) return;
    setActionError("");
    const moved = await library.moveDocument(moveModal.document, folderId);
    if (moved) {
      await search.runSearch();
      closeMoveModal();
    }
  }

  async function submitAssignment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!assignmentModal.document || !assignmentForm.userId) return;
    setActionError("");
    try {
      await assignDocument(
        documentAccessClient,
        assignmentModal.document.documentId,
        assignmentForm,
      );
      setAssignmentModal({ open: false, document: null });
      await managed.reload();
    } catch (caughtError) {
      const requestError = toError(caughtError);
      setActionError(requestError.message);
    }
  }

  async function updateAssignment(assignment: Assignment, action: string) {
    setActionError("");
    try {
      if (action === "accept")
        await acceptAssignment(documentAccessClient, assignment.assignmentId);
      if (action === "reject")
        await rejectAssignment(
          documentAccessClient,
          assignment.assignmentId,
          "Rechazado desde Blandskron Documental",
        );
      if (action === "sign")
        await signAssignment(
          documentAccessClient,
          assignment.assignmentId,
          currentUser?.displayName || currentUser?.username || "Firma digital",
        );
      if (action === "cancel")
        await cancelAssignment(documentAccessClient, assignment.assignmentId);
      await Promise.all([
        assigned.reload(),
        managed.reload(),
        notificationList.reload(),
      ]);
    } catch (caughtError) {
      const requestError = toError(caughtError);
      setActionError(requestError.message);
      if (requestError.status === 409) {
        await Promise.all([
          assigned.reload(),
          managed.reload(),
          notificationList.reload(),
        ]);
      }
    }
  }

  async function readNotification(notification: Notification) {
    try {
      await markNotificationRead(
        documentAccessClient,
        notification.notificationId,
      );
      await notificationList.reload();
    } catch (caughtError) {
      const requestError = toError(caughtError);
      setActionError(requestError.message);
    }
  }

  function closePreview() {
    if (preview?.url) URL.revokeObjectURL(preview.url);
    setPreview(null);
  }

  const isFoldersView = activeView === appRoutes.documentFolders;
  const isFavoritesView = activeView === appRoutes.documentFavorites;
  const isAssignmentsView = activeView === appRoutes.documentAssignments;
  const isManagedView = activeView === appRoutes.documentManaged;
  const isNotificationsView = activeView === appRoutes.documentNotifications;
  const activeDocuments = isFavoritesView
    ? library.favoriteDocuments
    : isFoldersView && library.selectedFolder
      ? library.folderDocuments
      : showRecent
        ? library.recentDocuments
        : search.documents;

  const documentPageKey = isFavoritesView
    ? "favorites"
    : isFoldersView
      ? "content"
      : showRecent
        ? "recent"
        : null;
  const displayedDocumentCount = isAssignmentsView
    ? assignedDocuments.length
    : isManagedView
      ? managedDocuments.length
      : isNotificationsView || (isFoldersView && !library.selectedFolder)
        ? 0
        : activeDocuments.length;

  const totalDocsCount = library.recentDocuments.length;
  const totalFavoritesCount = library.favoriteDocuments.length;
  const totalFoldersCount = library.folders.length;

  const combinedError =
    (!isFoldersView &&
    !isFavoritesView &&
    !isAssignmentsView &&
    !isManagedView &&
    !isNotificationsView
      ? search.error
      : "") ||
    drive.error ||
    importing.error ||
    actionError ||
    assigned.error ||
    managed.error ||
    notificationList.error ||
    library.error;

  return (
    <AppShell
      sidebarOpen={sidebarOpen}
      onSidebarChange={setSidebarOpen}
      sidebar={
        <Sidebar
          collapsed={!sidebarOpen}
          activeConversation={activeConversation}
          activeRoute={activeView}
          conversations={conversations}
          onClose={() => setSidebarOpen(false)}
          onOpen={() => setSidebarOpen(true)}
          onCreateConversation={createNewConversation}
          onDeleteConversation={deleteConversation}
          onLogout={logout}
          onNavigate={onNavigate}
          onSelectConversation={setActiveId}
          user={currentUser}
        />
      }
    >
      <main
        id="main-content"
        tabIndex={-1}
        className="document-search-page blandskron-screen"
      >
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleUploadFile}
          style={{ display: "none" }}
        />

        <section className="document-search-content">
          {/* Cabecera de Página */}
          <div className="library-title-row">
            <div>
              <h1>Documentos</h1>
              <p>Gestiona y organiza todos tus archivos empresariales</p>
            </div>
            <div className="library-header-actions">
              {hasTenantPermission(currentUser, "use_google_drive") && (
                <button
                  className="action-button-secondary"
                  type="button"
                  disabled={drive.busy}
                  onClick={handleOpenDriveModal}
                >
                  <Cloud size={16} /> Google Drive
                </button>
              )}
              <button
                className="action-button-secondary"
                type="button"
                disabled={library.isLoading}
                onClick={() =>
                  Promise.all([library.refreshLibrary(), search.runSearch()])
                }
              >
                Actualizar biblioteca
              </button>
              <button
                className="action-button-secondary"
                type="button"
                onClick={() => setCreateFolderModalOpen(true)}
              >
                <Plus size={16} /> Nueva Carpeta
              </button>
              <button
                className="action-button-primary"
                type="button"
                onClick={handleTriggerUpload}
                disabled={!canUploadDocuments}
              >
                <Upload size={16} /> Subir Archivo
              </button>
            </div>
          </div>

          {/* Tarjetas de Estadísticas KPI */}
          <div className="kpi-container">
            <article className="kpi-card">
              <span className="kpi-card-title">Recientes cargados</span>
              <strong className="kpi-card-value">{totalDocsCount}</strong>
              <span className="kpi-card-sub">
                {totalFavoritesCount} favoritos cargados
              </span>
            </article>
            <article className="kpi-card">
              <span className="kpi-card-title">Carpetas raíz cargadas</span>
              <strong className="kpi-card-value">{totalFoldersCount}</strong>
              <span className="kpi-card-sub">Organización personal</span>
            </article>
            <article className="kpi-card">
              <span className="kpi-card-title">Documentos en pantalla</span>
              <strong className="kpi-card-value">
                {displayedDocumentCount}
              </strong>
              <span className="kpi-card-sub">Registros cargados</span>
            </article>
            <article className="kpi-card">
              <span className="kpi-card-title">Pendientes cargados</span>
              <strong className="kpi-card-value">
                {
                  assignedDocuments.filter((item) => item.status === "PENDING")
                    .length
                }
              </strong>
              <span className="kpi-card-sub">
                {
                  notifications.filter((item) => item.status === "UNREAD")
                    .length
                }{" "}
                alertas
              </span>
            </article>
          </div>

          {/* Pestañas de Sub-Navegación */}
          <div className="documents-subtabs">
            <button
              className={`documents-subtab-btn ${!showRecent && activeView === appRoutes.documents ? "active" : ""}`}
              aria-current={
                !showRecent && activeView === appRoutes.documents
                  ? "page"
                  : undefined
              }
              onClick={() => {
                setShowRecent(false);
                onNavigate?.(appRoutes.documents);
              }}
              type="button"
            >
              <FileText size={15} />
              Todos
            </button>
            <button
              className={`documents-subtab-btn ${showRecent && activeView === appRoutes.documents ? "active" : ""}`}
              aria-current={
                showRecent && activeView === appRoutes.documents
                  ? "page"
                  : undefined
              }
              type="button"
              onClick={() => {
                setShowRecent(true);
                onNavigate?.(appRoutes.documents);
              }}
            >
              Actualizados recientemente
            </button>
            <button
              className={`documents-subtab-btn ${isAssignmentsView ? "active" : ""}`}
              aria-current={isAssignmentsView ? "page" : undefined}
              onClick={() => onNavigate?.(appRoutes.documentAssignments)}
              type="button"
            >
              <Check size={15} />
              Asignados a mi
            </button>
            <button
              className={`documents-subtab-btn ${isManagedView ? "active" : ""}`}
              aria-current={isManagedView ? "page" : undefined}
              onClick={() => onNavigate?.(appRoutes.documentManaged)}
              type="button"
            >
              <Send size={15} />
              Gestionados
            </button>
            <button
              className={`documents-subtab-btn ${isNotificationsView ? "active" : ""}`}
              aria-current={isNotificationsView ? "page" : undefined}
              onClick={() => onNavigate?.(appRoutes.documentNotifications)}
              type="button"
            >
              <Bell size={15} />
              Notificaciones
            </button>
            <button
              className={`documents-subtab-btn ${isFoldersView ? "active" : ""}`}
              aria-current={isFoldersView ? "page" : undefined}
              onClick={() => onNavigate?.(appRoutes.documentFolders)}
              type="button"
            >
              <Folder size={15} />
              Carpetas
            </button>
            <button
              className={`documents-subtab-btn ${isFavoritesView ? "active" : ""}`}
              aria-current={isFavoritesView ? "page" : undefined}
              onClick={() => onNavigate?.(appRoutes.documentFavorites)}
              type="button"
            >
              <Star size={15} />
              Favoritos
            </button>
          </div>

          {/* Controles de Búsqueda y Filtros */}
          {!isFoldersView &&
            !isFavoritesView &&
            !showRecent &&
            !isAssignmentsView &&
            !isManagedView &&
            !isNotificationsView && (
              <div className="documents-control-row">
                <DocumentSearchBar
                  isLoading={search.isLoading}
                  query={search.query}
                  onQueryChange={search.setQuery}
                  onSearch={search.runSearch}
                />
                <div
                  className="layout-toggle-group"
                  role="group"
                  aria-label="Presentación de documentos"
                >
                  <button
                    className={`layout-btn ${viewMode === "grid" ? "active" : ""}`}
                    onClick={() => setViewMode("grid")}
                    type="button"
                    aria-label="Vista cuadrícula"
                    aria-pressed={viewMode === "grid"}
                  >
                    <LayoutGrid size={17} />
                  </button>
                  <button
                    className={`layout-btn ${viewMode === "list" ? "active" : ""}`}
                    onClick={() => setViewMode("list")}
                    type="button"
                    aria-label="Vista lista"
                    aria-pressed={viewMode === "list"}
                  >
                    <List size={17} />
                  </button>
                </div>
              </div>
            )}

          {/* Contenedor de Vista de Carpetas */}
          {isFoldersView && (
            <section className="folder-management">
              <div className="section-header-row">
                <h3>Carpetas raíz</h3>
                <span className="section-header-badge">
                  {library.folders.length} carpetas cargadas
                </span>
              </div>

              <div className="folder-grid">
                {library.folders.map((folder, index) => {
                  const colors = [
                    "#3b82f6",
                    "#10b981",
                    "#a855f7",
                    "#ef4444",
                    "#f97316",
                    "#eab308",
                  ];
                  const color = colors[index % colors.length];
                  return (
                    <button
                      className={`folder-card ${library.selectedFolder?.folderId === folder.folderId ? "active" : ""}`}
                      key={folder.folderId}
                      onClick={() => library.openFolder(folder)}
                      type="button"
                    >
                      <div
                        className="folder-card-color-icon"
                        style={{ backgroundColor: color }}
                      >
                        <Folder size={20} color="#ffffff" fill="#ffffff" />
                      </div>
                      <div className="folder-card-info">
                        <span className="folder-card-name">{folder.name}</span>
                        <small className="folder-card-count">
                          {formatFolderCount(folder)} archivos
                        </small>
                        <small className="folder-card-time">
                          {formatDate(folder.updatedAt)}
                        </small>
                      </div>
                    </button>
                  );
                })}
                {!library.isLoading && library.folders.length === 0 && (
                  <div className="empty-documents">
                    Aún no tienes carpetas creadas.
                  </div>
                )}
              </div>
              <LibraryPagination
                page={library.pages.folders}
                label="carpetas"
                onLoadMore={() => library.loadMore("folders")}
              />

              {library.selectedFolder && (
                <div className="selected-folder-row">
                  <div>
                    <strong>{library.selectedFolder?.name}</strong>
                    <span>
                      {library.folderDocuments.length} documentos cargados
                    </span>
                  </div>
                  <button type="button" onClick={library.closeFolder}>
                    <X size={15} /> Cerrar carpeta
                  </button>
                </div>
              )}
            </section>
          )}

          {combinedError && (
            <div role="alert" className="login-error">
              {combinedError}
            </div>
          )}

          {/* Contenedor de Vista de Documentos */}
          {(isAssignmentsView || isManagedView) && (
            <AssignmentWorkflowList
              assignments={
                isAssignmentsView ? assignedDocuments : managedDocuments
              }
              pagination={isAssignmentsView ? assigned : managed}
              mode={isAssignmentsView ? "assigned" : "managed"}
              onAction={updateAssignment}
              onDownload={(assignment) =>
                downloadSelectedDocument({
                  documentId: assignment.documentId,
                  filename: `documento-${assignment.documentId}`,
                  status: "PROCESSED",
                })
              }
            />
          )}

          {isNotificationsView && (
            <section className="documents-list-section">
              <div className="section-header-row">
                <h3>Notificaciones</h3>
                <span className="section-header-badge">
                  {notifications.length} eventos cargados
                </span>
              </div>
              <div className="workflow-list">
                {notifications.map((notification) => (
                  <article
                    className="workflow-card"
                    key={notification.notificationId}
                    style={{ gridTemplateColumns: "1fr" }}
                  >
                    <div>
                      <strong>{notification.title}</strong>
                      <p>{notification.body}</p>
                      {notification.status === "UNREAD" && (
                        <button
                          type="button"
                          className="action-button-secondary"
                          onClick={() => readNotification(notification)}
                        >
                          Marcar como leída
                        </button>
                      )}
                      <span>{formatDate(notification.createdAt)}</span>
                    </div>
                  </article>
                ))}
                {!notifications.length && !notificationList.loading && (
                  <div className="empty-documents">
                    No tienes notificaciones.
                  </div>
                )}
                <WorkflowPagination page={notificationList} />
              </div>
            </section>
          )}

          {(!isFoldersView || library.selectedFolder) &&
            !isAssignmentsView &&
            !isManagedView &&
            !isNotificationsView && (
              <section className="documents-list-section">
                <div
                  className="section-header-row"
                  style={{ marginTop: isFoldersView ? "24px" : "0" }}
                >
                  <h3>
                    {isFavoritesView
                      ? "Favoritos"
                      : isFoldersView
                        ? library.selectedFolder?.name
                        : showRecent
                          ? "Actualizados recientemente"
                          : "Todos los Documentos"}
                  </h3>
                  <span className="section-header-badge">
                    {activeDocuments.length} documentos cargados
                  </span>
                </div>

                <div className={`document-results ${viewMode}`}>
                  {activeDocuments.map((document) => (
                    <DocumentResultCard
                      key={document.documentId}
                      document={document}
                      isFavorite={library.favoriteIds.has(document.documentId)}
                      folderName={
                        isFoldersView ? library.selectedFolder?.name : undefined
                      }
                      onDelete={openDeleteModal}
                      onAssign={openAssignmentModal}
                      onDownload={downloadSelectedDocument}
                      onMoveToFolder={openMoveModal}
                      onPreview={previewDocument}
                      onSendToChat={sendToChat}
                      onToggleFavorite={library.toggleFavorite}
                      permissions={{
                        assign: canAssignDocuments,
                        delete: canManageDocuments,
                        download: canDownloadDocuments,
                      }}
                    />
                  ))}
                  {!search.isLoading &&
                    !library.isLoading &&
                    activeDocuments.length === 0 && (
                      <div className="empty-documents">
                        {emptyStateText(activeView, library.selectedFolder)}
                      </div>
                    )}
                </div>
                {documentPageKey && (
                  <LibraryPagination
                    page={library.pages[documentPageKey]}
                    onLoadMore={() => library.loadMore(documentPageKey)}
                  />
                )}
              </section>
            )}
        </section>

        <TransferWarning
          warning={transfers.warning}
          onDismiss={transfers.dismissWarning}
        />
        <TransferModal
          error={transfers.error}
          isClearing={transfers.isClearing}
          hasMore={transfers.hasMore}
          onLoadMore={transfers.loadMore}
          onRefresh={transfers.refreshTransfers}
          isLoading={transfers.isLoading}
          isOpen={transfersOpen}
          onClearHistory={transfers.clearHistory}
          onClose={() => setTransfersOpen(false)}
          transfers={transfers.transfers}
        />
        <DocumentPreviewModal
          preview={preview}
          onClose={closePreview}
          onDownload={() =>
            preview?.document && downloadSelectedDocument(preview.document)
          }
        />
        <ConfirmModal
          isOpen={deleteModal.open}
          title="Confirmar eliminación"
          message={`¿Seguro que deseas eliminar "${deleteModal.document?.filename || "este documento"}"? Esta acción no se puede deshacer.`}
          onCancel={closeDeleteModal}
          onConfirm={confirmDeleteDocument}
        />
        <MoveDocumentModal
          document={moveModal.document}
          folders={library.folders}
          page={library.pages.folders}
          error={library.error}
          onLoadMore={() => library.loadMore("folders")}
          isOpen={moveModal.open}
          onClose={closeMoveModal}
          onMove={moveSelectedDocument}
        />
        <AssignDocumentModal
          document={assignmentModal.document}
          form={assignmentForm}
          isOpen={assignmentModal.open}
          users={tenantUsers}
          onChange={setAssignmentForm}
          onClose={() => setAssignmentModal({ open: false, document: null })}
          onSubmit={submitAssignment}
        />
        <GoogleDriveImportModal
          history={
            <DriveHistory
              client={googleDriveImportClient}
              scope={profileSessionKey}
            />
          }
          onCancel={() => importing.controller.cancel()}
          error={drive.error || importing.error}
          operationScope={profileSessionKey}
          connection={driveConnection}
          fileIds={driveFileIds}
          isBusy={driveImportBusy || drive.busy}
          isOpen={driveModalOpen}
          pickerConfigured={Boolean(
            env.googleClientId && env.googlePickerApiKey,
          )}
          selectedFiles={selectedDriveFiles}
          onClose={() => {
            importing.controller.cancel(false);
            setDriveModalOpen(false);
          }}
          onConnect={handleConnectDrive}
          onDisconnect={drive.disconnect}
          onFileIdsChange={(value) => {
            setDriveFileIds(value);
            setSelectedDriveFiles([]);
          }}
          onImport={handleImportDriveFiles}
          onOpenPicker={handleOpenGooglePicker}
        />

        {createFolderModalOpen && (
          <CreateFolderDialog
            error={library.error}
            onClose={() => setCreateFolderModalOpen(false)}
            onCreate={async (name) => {
              const folder = await library.addFolder(name);
              if (!folder) return false;
              await library.openFolder(folder);
              return true;
            }}
          />
        )}
      </main>
    </AppShell>
  );
}

function emptyStateText(activeView: string, selectedFolder: FolderItem | null) {
  if (activeView === appRoutes.documentFavorites)
    return "No tienes documentos favoritos.";
  if (activeView === appRoutes.documentFolders && selectedFolder)
    return "Esta carpeta no tiene documentos.";
  return "No hay documentos para estos filtros.";
}
