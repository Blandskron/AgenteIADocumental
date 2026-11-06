import { useEffect, useState, useRef } from "react";
import { Bell, Check, Cloud, Folder, Menu, Plus, Star, X, Upload, Filter, LayoutGrid, List, FileText, Send } from "lucide-react";

import { env } from "../../app/config/env";
import { appRoutes } from "../../app/router/routes";
import { useAuthContext } from "../../app/providers/AuthProvider";
import { AppShell } from "../../shared/layouts/AppShell";
import { IconButton } from "../../shared/components/IconButton/IconButton";
import { TransferModal } from "../../shared/components/TransferModal/TransferModal";
import { useConversations } from "../../features/conversations/hooks/useConversations";
import { useDocumentLibrary } from "../../features/document-library/hooks/useDocumentLibrary";
import { transferFailureUpdate } from "../../features/transfers/lib/failure-update";
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
} from "../../features/document-access/api/document-access.api";
import { useWorkflowList } from "../../features/document-access/hooks/useWorkflowList";
import { DocumentPreviewModal } from "../../features/document-access/ui/DocumentPreviewModal";
import { buildChatSelection } from "../../features/document-search/api/document-search.api";
import { useDocumentSearch } from "../../features/document-search/hooks/useDocumentSearch";
import { DocumentResultCard } from "../../features/document-search/ui/DocumentResultCard";
import { DocumentSearchBar } from "../../features/document-search/ui/DocumentSearchBar";
import { useTransfers } from "../../features/transfers/hooks/useTransfers";
import { ConfirmModal } from "../../shared/components/ConfirmModal/ConfirmModal";
import { Sidebar } from "../../widgets/Sidebar/Sidebar";

// Nuevos importadores para gestión de carga y mapeo de carpetas
import { uploadDocument } from "../../features/documents/api/document.api";
import { hasTenantPermission, isTenantAdmin } from "../../entities/auth/model/auth.user";
import { listUsers } from "../../features/auth/api/user-management.api";
import { waitForDocumentProcessed } from "../../features/documents/api/document-status.poller";
import { isDocumentProcessed } from "../../features/documents/lib/document-status";
import { LibraryPagination } from "../../features/document-library/ui/LibraryPagination";
import {
  connectGoogleDrive,
  getGoogleDriveAuthUrl,
  getGoogleDriveConnection,
  importGoogleDriveFiles,
} from "../../features/google-drive-import/api/google-drive-import.api";
import { openGoogleDrivePicker } from "../../features/google-drive-import/google-picker";
import { getImportWarning } from "../../features/google-drive-import/import-result";

export function DocumentSearchPage({ activeView = appRoutes.documents, onNavigate }) {
  const {
    conversationClient,
    currentUser,
    documentAccessClient,
    documentLibraryClient,
    documentSearchClient,
    documentTransferClient,
    documentClient,
    googleDriveImportClient,
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
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [preview, setPreview] = useState(null);
  const [actionError, setActionError] = useState("");
  const [transfersOpen, setTransfersOpen] = useState(false);
  const [deleteModal, setDeleteModal] = useState({ open: false, document: null });
  const [moveModal, setMoveModal] = useState({ open: false, document: null });
  const [newFolderName, setNewFolderName] = useState("");
  const [createFolderModalOpen, setCreateFolderModalOpen] = useState(false);
  const [assignmentModal, setAssignmentModal] = useState({ open: false, document: null });
  const [assignmentForm, setAssignmentForm] = useState({ userId: "", allowDownload: true, dueAt: "" });
  const [tenantUsers, setTenantUsers] = useState([]);
  const assigned = useWorkflowList(documentAccessClient, listAssignedToMe);
  const managed = useWorkflowList(documentAccessClient, listManagedByMe);
  const notificationList = useWorkflowList(documentAccessClient, listNotifications);
  const assignedDocuments = assigned.items;
  const managedDocuments = managed.items;
  const notifications = notificationList.items;
  const [viewMode, setViewMode] = useState("grid");
  const [showRecent, setShowRecent] = useState(false);
  const [driveModalOpen, setDriveModalOpen] = useState(false);
  const [driveConnection, setDriveConnection] = useState({ connected: false });
  const [driveFileIds, setDriveFileIds] = useState("");
  const [selectedDriveFiles, setSelectedDriveFiles] = useState([]);
  const [driveImportBusy, setDriveImportBusy] = useState(false);
  const fileInputRef = useRef(null);
  const canAssignDocuments = isTenantAdmin(currentUser) || hasTenantPermission(currentUser, "assign_documents");
  const canUploadDocuments = isTenantAdmin(currentUser) || hasTenantPermission(currentUser, "upload_documents");
  const canDownloadDocuments = isTenantAdmin(currentUser) || hasTenantPermission(currentUser, "download_documents");
  const canManageDocuments = isTenantAdmin(currentUser) || hasTenantPermission(currentUser, "manage_documents");

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

  useEffect(() => {
    if (activeView !== appRoutes.documentFolders) {
      library.closeFolder();
    }
  }, [activeView]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    if (!code || !googleDriveImportClient) return;

    connectGoogleDrive(googleDriveImportClient, code)
      .then((connection) => {
        setDriveConnection(connection);
        setActionError("");
        window.history.replaceState({}, document.title, window.location.pathname);
      })
      .catch((error) => setActionError(error.message));
  }, [googleDriveImportClient]);

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
    try {
      setDriveConnection(await getGoogleDriveConnection(googleDriveImportClient));
    } catch (error) {
      setActionError(error.message);
    }
  };

  const handleConnectDrive = async () => {
    setActionError("");
    try {
      const payload = await getGoogleDriveAuthUrl(googleDriveImportClient, window.location.href);
      window.location.assign(payload.authorization_url);
    } catch (error) {
      setActionError(error.message);
    }
  };

  const handleImportDriveFiles = async (event) => {
    event.preventDefault();
    const files = selectedDriveFiles.length
      ? selectedDriveFiles
      : driveFileIds
          .split(/[\n,]/)
          .map((value) => value.trim())
          .filter(Boolean)
          .map((fileId) => ({ fileId }));
    if (!files.length) return;

    setDriveImportBusy(true);
    setActionError("");
    try {
      const imported = await importGoogleDriveFiles(googleDriveImportClient, {
        files,
        folderId: library.selectedFolder?.folderId,
        metadata: { imported_from_ui: true },
      });
      setDriveFileIds("");
      setSelectedDriveFiles([]);
      setDriveModalOpen(false);
      await search.runSearch();
      await library.refreshLibrary();
      setActionError(getImportWarning(imported));
    } catch (error) {
      setActionError(error.message);
    } finally {
      setDriveImportBusy(false);
    }
  };

  const handleOpenGooglePicker = async () => {
    setActionError("");
    try {
      const pickedFiles = await openGoogleDrivePicker({
        appId: env.googlePickerAppId,
        clientId: env.googleClientId,
        developerKey: env.googlePickerApiKey,
      });
      if (!pickedFiles.length) return;
      setSelectedDriveFiles(pickedFiles);
      setDriveFileIds(pickedFiles.map((file) => file.fileId).join("\n"));
    } catch (error) {
      setActionError(error.message);
    }
  };

  const handleUploadFile = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setActionError("");
    let transfer = null;
    try {
      transfer = await transfers.recordTransfer({
        filename: file.name,
        direction: "UPLOAD",
        status: "RUNNING",
        progress: 15,
        size_bytes: file.size,
      });

      const doc = await uploadDocument(documentClient, { file });

      await transfers.patchTransfer(transfer?.transferId, {
        document_id: doc.documentId,
        progress: isDocumentProcessed(doc.status) ? 100 : 65,
        status: isDocumentProcessed(doc.status) ? "COMPLETED" : "RUNNING",
      });

      if (!isDocumentProcessed(doc.status)) {
        await waitForDocumentProcessed(documentClient, doc.documentId);
        await transfers.patchTransfer(transfer?.transferId, {
          document_id: doc.documentId,
          progress: 100,
          status: "COMPLETED",
        });
      }

      await search.runSearch();
      await library.refreshLibrary();
    } catch (err) {
      if (transfer) {
        await transfers.patchTransfer(transfer?.transferId, transferFailureUpdate(err));
      }
      setActionError(err.message);
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  async function sendToChat(document) {
    if (!activeConversation?.id) return;
    const selection = await buildChatSelection(documentSearchClient, {
      documentIds: [document.documentId],
      sessionId: activeConversation.id,
    });
    const message = `Documento seleccionado: ${document.filename}. Ya puedes pedirme que lo analice.`;
    setSelectedDocuments(selection.documents);
    if (!activeConversation.messages?.some((item) => item.content === message)) {
      addMessage({ role: "assistant", content: message, sources: [] });
    }
    onNavigate?.(appRoutes.chat);
  }

  async function previewDocument(document) {
    setActionError("");
    if (preview?.url) URL.revokeObjectURL(preview.url);
    try {
      setPreview({
        ...(await getDocumentPreview(documentAccessClient, document)),
        document,
      });
    } catch (requestError) {
      setActionError(requestError.message);
    }
  }

  async function downloadSelectedDocument(document) {
    setActionError("");
    let transfer = null;
    try {
      transfer = await transfers.recordTransfer({
        filename: document.filename,
        direction: "DOWNLOAD",
        status: "RUNNING",
        progress: 40,
        document_id: document.documentId,
      });
      await downloadDocument(documentAccessClient, document);
      await transfers.patchTransfer(transfer?.transferId, {
        status: "COMPLETED",
        progress: 100,
        document_id: document.documentId,
      });
    } catch (requestError) {
      await transfers.patchTransfer(transfer?.transferId, transferFailureUpdate(requestError));
      setActionError(requestError.message);
    }
  }

  function openDeleteModal(document) {
    setDeleteModal({ open: true, document });
  }

  function closeDeleteModal() {
    setDeleteModal({ open: false, document: null });
  }

  function openMoveModal(document) {
    setMoveModal({ open: true, document });
  }

  function openAssignmentModal(document) {
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
      await deleteDocument(documentAccessClient, deleteModal.document.documentId);
      await search.runSearch();
      await library.refreshLibrary();
      closeDeleteModal();
    } catch (requestError) {
      setActionError(requestError.message);
    }
  }

  async function handleCreateFolder(event) {
    event.preventDefault();
    const folder = await library.addFolder(newFolderName);
    if (folder) {
      setNewFolderName("");
      await library.openFolder(folder);
    }
  }

  async function moveSelectedDocument(folderId = null) {
    if (!moveModal.document) return;
    setActionError("");
    const moved = await library.moveDocument(moveModal.document, folderId);
    if (moved) {
      await search.runSearch();
      closeMoveModal();
    }
  }

  async function submitAssignment(event) {
    event.preventDefault();
    if (!assignmentModal.document || !assignmentForm.userId) return;
    setActionError("");
    try {
      await assignDocument(documentAccessClient, assignmentModal.document.documentId, assignmentForm);
      setAssignmentModal({ open: false, document: null });
      await managed.reload();
    } catch (requestError) {
      setActionError(requestError.message);
    }
  }

  async function updateAssignment(assignment, action) {
    setActionError("");
    try {
      if (action === "accept") await acceptAssignment(documentAccessClient, assignment.assignmentId);
      if (action === "reject") await rejectAssignment(documentAccessClient, assignment.assignmentId, "Rechazado desde Blandskron Documental");
      if (action === "sign") await signAssignment(documentAccessClient, assignment.assignmentId, currentUser?.displayName || currentUser?.username || "Firma digital");
      if (action === "cancel") await cancelAssignment(documentAccessClient, assignment.assignmentId);
      await Promise.all([assigned.reload(), managed.reload(), notificationList.reload()]);
    } catch (requestError) {
      setActionError(requestError.message);
      if (requestError.status === 409) {
        await Promise.all([assigned.reload(), managed.reload(), notificationList.reload()]);
      }
    }
  }

  async function readNotification(notification) {
    try {
      await markNotificationRead(documentAccessClient, notification.notificationId);
      await notificationList.reload();
    } catch (requestError) {
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
      : showRecent ? library.recentDocuments : search.documents;

  const documentPageKey = isFavoritesView ? "favorites" : isFoldersView ? "content" : showRecent ? "recent" : null;
  const displayedDocumentCount = isAssignmentsView ? assignedDocuments.length : isManagedView ? managedDocuments.length
    : isNotificationsView || (isFoldersView && !library.selectedFolder) ? 0 : activeDocuments.length;

  const totalDocsCount = library.recentDocuments.length;
  const totalFavoritesCount = library.favoriteDocuments.length;
  const totalFoldersCount = library.folders.length;

  const combinedError = (!isFoldersView && !isFavoritesView && !isAssignmentsView && !isManagedView && !isNotificationsView ? search.error : "") || actionError || assigned.error || managed.error || notificationList.error || library.error;

  return (
    <AppShell
      sidebarOpen={sidebarOpen}
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
      <main className="document-search-page blandskron-screen">
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
              <button className="action-button-secondary" type="button" disabled={library.isLoading}
                onClick={() => Promise.all([library.refreshLibrary(), search.runSearch()])}>
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
              <span className="kpi-card-sub">{totalFavoritesCount} favoritos cargados</span>
            </article>
            <article className="kpi-card">
              <span className="kpi-card-title">Carpetas raíz cargadas</span>
              <strong className="kpi-card-value">{totalFoldersCount}</strong>
              <span className="kpi-card-sub">Organización personal</span>
            </article>
            <article className="kpi-card">
              <span className="kpi-card-title">Documentos en pantalla</span>
              <strong className="kpi-card-value">{displayedDocumentCount}</strong>
              <span className="kpi-card-sub">Registros cargados</span>
            </article>
            <article className="kpi-card">
              <span className="kpi-card-title">Pendientes cargados</span>
              <strong className="kpi-card-value">{assignedDocuments.filter((item) => item.status === "PENDING").length}</strong>
              <span className="kpi-card-sub">{notifications.filter((item) => item.status === "UNREAD").length} alertas</span>
            </article>
          </div>

          {/* Pestañas de Sub-Navegación */}
          <div className="documents-subtabs">
            <button
              className={`documents-subtab-btn ${!showRecent && activeView === appRoutes.documents ? "active" : ""}`}
              onClick={() => { setShowRecent(false); onNavigate?.(appRoutes.documents); }}
              type="button"
            >
              <FileText size={15} />
              Todos
            </button>
            <button className={`documents-subtab-btn ${showRecent && activeView === appRoutes.documents ? "active" : ""}`}
              type="button" onClick={() => { setShowRecent(true); onNavigate?.(appRoutes.documents); }}>
              Actualizados recientemente
            </button>
            <button
              className={`documents-subtab-btn ${isAssignmentsView ? "active" : ""}`}
              onClick={() => onNavigate?.(appRoutes.documentAssignments)}
              type="button"
            >
              <Check size={15} />
              Asignados a mi
            </button>
            <button
              className={`documents-subtab-btn ${isManagedView ? "active" : ""}`}
              onClick={() => onNavigate?.(appRoutes.documentManaged)}
              type="button"
            >
              <Send size={15} />
              Gestionados
            </button>
            <button
              className={`documents-subtab-btn ${isNotificationsView ? "active" : ""}`}
              onClick={() => onNavigate?.(appRoutes.documentNotifications)}
              type="button"
            >
              <Bell size={15} />
              Notificaciones
            </button>
            <button
              className={`documents-subtab-btn ${isFoldersView ? "active" : ""}`}
              onClick={() => onNavigate?.(appRoutes.documentFolders)}
              type="button"
            >
              <Folder size={15} />
              Carpetas
            </button>
            <button
              className={`documents-subtab-btn ${isFavoritesView ? "active" : ""}`}
              onClick={() => onNavigate?.(appRoutes.documentFavorites)}
              type="button"
            >
              <Star size={15} />
              Favoritos
            </button>
          </div>

          {/* Controles de Búsqueda y Filtros */}
          {!isFoldersView && !isFavoritesView && !showRecent && !isAssignmentsView && !isManagedView && !isNotificationsView && (
            <div className="documents-control-row">
              <DocumentSearchBar
                isLoading={search.isLoading}
                query={search.query}
                onQueryChange={search.setQuery}
                onSearch={search.runSearch}
              />
              <button className="control-filter-btn" type="button" aria-label="Filtrar">
                <Filter size={17} />
              </button>
              <div className="layout-toggle-group">
                <button 
                  className={`layout-btn ${viewMode === "grid" ? "active" : ""}`} 
                  onClick={() => setViewMode("grid")}
                  type="button"
                  aria-label="Vista cuadrícula"
                >
                  <LayoutGrid size={17} />
                </button>
                <button 
                  className={`layout-btn ${viewMode === "list" ? "active" : ""}`} 
                  onClick={() => setViewMode("list")}
                  type="button"
                  aria-label="Vista lista"
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
                <span className="section-header-badge">{library.folders.length} carpetas cargadas</span>
              </div>

              <div className="folder-grid">
                {library.folders.map((folder, index) => {
                  const colors = ["#3b82f6", "#10b981", "#a855f7", "#ef4444", "#f97316", "#eab308"];
                  const color = colors[index % colors.length];
                  return (
                    <button
                      className={`folder-card ${library.selectedFolder?.folderId === folder.folderId ? "active" : ""}`}
                      key={folder.folderId}
                      onClick={() => library.openFolder(folder)}
                      type="button"
                    >
                      <div className="folder-card-color-icon" style={{ backgroundColor: color }}>
                        <Folder size={20} color="#ffffff" fill="#ffffff" />
                      </div>
                      <div className="folder-card-info">
                        <span className="folder-card-name">{folder.name}</span>
                        <small className="folder-card-count">{formatFolderCount(folder)} archivos</small>
                        <small className="folder-card-time">{formatDate(folder.updatedAt)}</small>
                      </div>
                    </button>
                  );
                })}
                {!library.isLoading && library.folders.length === 0 && (
                  <div className="empty-documents">Aún no tienes carpetas creadas.</div>
                )}
              </div>
              <LibraryPagination page={library.pages.folders} label="carpetas" onLoadMore={() => library.loadMore("folders")} />

              {library.selectedFolder && (
                <div className="selected-folder-row">
                  <div>
                    <strong>{library.selectedFolder.name}</strong>
                    <span>{library.folderDocuments.length} documentos cargados</span>
                  </div>
                  <button type="button" onClick={library.closeFolder}>
                    <X size={15} /> Cerrar carpeta
                  </button>
                </div>
              )}
            </section>
          )}

          {combinedError && <div className="login-error">{combinedError}</div>}

          {/* Contenedor de Vista de Documentos */}
          {(isAssignmentsView || isManagedView) && (
            <AssignmentWorkflowList
              assignments={isAssignmentsView ? assignedDocuments : managedDocuments}
              pagination={isAssignmentsView ? assigned : managed}
              mode={isAssignmentsView ? "assigned" : "managed"}
              onAction={updateAssignment}
              onDownload={(assignment) =>
                downloadSelectedDocument({ documentId: assignment.documentId, filename: `documento-${assignment.documentId}` })
              }
            />
          )}

          {isNotificationsView && (
            <section className="documents-list-section">
              <div className="section-header-row">
                <h3>Notificaciones</h3>
                <span className="section-header-badge">{notifications.length} eventos cargados</span>
              </div>
              <div className="workflow-list">
                {notifications.map((notification) => (
                  <article className="workflow-card" key={notification.notificationId} style={{ gridTemplateColumns: "1fr" }}>
                    <div>
                      <strong>{notification.title}</strong>
                      <p>{notification.body}</p>
                      <span>{formatDate(notification.createdAt)}</span>
                    </div>
                  </article>
                ))}
                {!notifications.length && !notificationList.loading && <div className="empty-documents">No tienes notificaciones.</div>}
                <WorkflowPagination page={notificationList} />
              </div>
            </section>
          )}

          {(!isFoldersView || library.selectedFolder) && !isAssignmentsView && !isManagedView && !isNotificationsView && (
            <section className="documents-list-section">
              <div className="section-header-row" style={{ marginTop: isFoldersView ? "24px" : "0" }}>
                <h3>{isFavoritesView ? "Favoritos" : isFoldersView ? library.selectedFolder.name : showRecent ? "Actualizados recientemente" : "Todos los Documentos"}</h3>
                <span className="section-header-badge">{activeDocuments.length} documentos cargados</span>
              </div>

              <div className={`document-results ${viewMode}`}>
                {activeDocuments.map((document) => (
                  <DocumentResultCard
                    key={document.documentId}
                    document={document}
                    isFavorite={library.favoriteIds.has(document.documentId)}
                    folderName={isFoldersView ? library.selectedFolder?.name : undefined}
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
                {!search.isLoading && !library.isLoading && activeDocuments.length === 0 && (
                  <div className="empty-documents">{emptyStateText(activeView, library.selectedFolder)}</div>
                )}
              </div>
              {documentPageKey && <LibraryPagination page={library.pages[documentPageKey]} onLoadMore={() => library.loadMore(documentPageKey)} />}
            </section>
          )}
        </section>

        <TransferModal
          error={transfers.error}
          isLoading={transfers.isLoading}
          isOpen={transfersOpen}
          onClearHistory={transfers.clearHistory}
          onClose={() => setTransfersOpen(false)}
          transfers={transfers.transfers}
        />
        <DocumentPreviewModal
          preview={preview}
          onClose={closePreview}
          onDownload={() => preview?.document && downloadSelectedDocument(preview.document)}
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
          connection={driveConnection}
          fileIds={driveFileIds}
          isBusy={driveImportBusy}
          isOpen={driveModalOpen}
          pickerConfigured={Boolean(env.googleClientId && env.googlePickerApiKey)}
          selectedFiles={selectedDriveFiles}
          onClose={() => setDriveModalOpen(false)}
          onConnect={handleConnectDrive}
          onFileIdsChange={setDriveFileIds}
          onImport={handleImportDriveFiles}
          onOpenPicker={handleOpenGooglePicker}
        />

        {/* Modal de Creación de Carpeta */}
        {createFolderModalOpen && (
          <div className="move-document-backdrop" role="presentation" onClick={() => setCreateFolderModalOpen(false)}>
            <section
              className="move-document-modal"
              role="dialog"
              aria-modal="true"
              aria-labelledby="create-folder-title"
              onClick={(event) => event.stopPropagation()}
            >
              <header>
                <div>
                  <p>Crear nueva carpeta</p>
                  <h3 id="create-folder-title">Nueva Carpeta</h3>
                </div>
                <button className="icon-action-button" type="button" onClick={() => setCreateFolderModalOpen(false)} aria-label="Cerrar">
                  <X size={17} />
                </button>
              </header>
              <form onSubmit={async (e) => {
                e.preventDefault();
                const folder = await library.addFolder(newFolderName);
                if (folder) {
                  setNewFolderName("");
                  setCreateFolderModalOpen(false);
                  await library.openFolder(folder);
                }
              }} style={{ padding: "20px", display: "flex", flexDirection: "column", gap: "14px" }}>
                {library.error && <p role="alert">{library.error}</p>}
                <input
                  id="new-folder-name-input"
                  className="modal-input"
                  onChange={(event) => setNewFolderName(event.target.value)}
                  placeholder="Nombre de la carpeta"
                  value={newFolderName}
                  autoFocus
                  style={{
                    width: "100%",
                    padding: "10px 12px",
                    borderRadius: "8px",
                    border: "1px solid var(--line)",
                    background: "var(--panel-2)",
                    color: "var(--text)",
                    outline: "none"
                  }}
                />
                <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
                  <button className="modal-cancel-btn" type="button" onClick={() => setCreateFolderModalOpen(false)} style={{
                    padding: "8px 16px",
                    borderRadius: "8px",
                    border: "1px solid var(--line)",
                    background: "transparent",
                    color: "var(--text)",
                    cursor: "pointer"
                  }}>
                    Cancelar
                  </button>
                  <button className="modal-confirm-btn" type="submit" disabled={!newFolderName.trim()} style={{
                    padding: "8px 16px",
                    borderRadius: "8px",
                    border: "none",
                    background: "var(--text)",
                    color: "var(--black)",
                    fontWeight: "600",
                    cursor: "pointer",
                    opacity: newFolderName.trim() ? 1 : 0.5
                  }}>
                    Crear
                  </button>
                </div>
              </form>
            </section>
          </div>
        )}
      </main>
    </AppShell>
  );
}

function MoveDocumentModal({ document, folders, page, error, onLoadMore, isOpen, onClose, onMove }) {
  if (!isOpen) return null;

  return (
    <div className="move-document-backdrop" role="presentation" onClick={onClose}>
      <section
        className="move-document-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="move-document-title"
        onClick={(event) => event.stopPropagation()}
      >
        <header>
          <div>
            <p>Mover documento</p>
            <h3 id="move-document-title">{document?.filename || "Documento"}</h3>
          </div>
          <button className="icon-action-button" type="button" onClick={onClose} aria-label="Cerrar">
            <X size={17} />
          </button>
        </header>
        <div className="move-folder-list">
          {error && <p role="alert">{error}</p>}
          {folders.map((folder) => (
            <button key={folder.folderId} type="button" onClick={() => onMove(folder.folderId)}>
              <Folder size={18} />
              <span>{folder.name}</span>
              <small>{formatFolderCount(folder)} archivos</small>
            </button>
          ))}
          {!folders.length && !page.loading && <p>No tienes carpetas raíz creadas.</p>}
          <LibraryPagination page={page} label="carpetas raíz" onLoadMore={onLoadMore} />
        </div>
        <footer>
          <button type="button" onClick={() => onMove(null)}>
            Sacar de carpetas
          </button>
          <button type="button" onClick={onClose}>
            Cancelar
          </button>
        </footer>
      </section>
    </div>
  );
}

function GoogleDriveImportModal({
  connection,
  fileIds,
  isBusy,
  isOpen,
  pickerConfigured,
  selectedFiles = [],
  onClose,
  onConnect,
  onFileIdsChange,
  onImport,
  onOpenPicker,
}) {
  if (!isOpen) return null;

  return (
    <div className="move-document-backdrop" role="presentation" onClick={onClose}>
      <section
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
          <button className="icon-action-button" type="button" onClick={onClose} aria-label="Cerrar">
            <X size={17} />
          </button>
        </header>
        <form className="google-drive-import-form" onSubmit={onImport}>
          <div className={`google-drive-status ${connection?.connected ? "connected" : ""}`}>
            <Cloud size={18} />
            <span>
              {connection?.connected
                ? `Conectado${connection.providerAccountEmail ? ` como ${connection.providerAccountEmail}` : ""}`
                : "Conecta Google Drive para importar archivos seleccionados."}
            </span>
          </div>
          {!connection?.connected && (
            <button className="action-button-primary" type="button" onClick={onConnect}>
              <Cloud size={16} /> Conectar Google Drive
            </button>
          )}
          {connection?.connected && (
            <>
              <button
                className="action-button-primary"
                type="button"
                onClick={onOpenPicker}
                disabled={!pickerConfigured || isBusy}
              >
                <Cloud size={16} /> Abrir selector de Drive
              </button>
              {!pickerConfigured && (
                <p className="google-drive-help">
                  Falta VITE_GOOGLE_PICKER_API_KEY para abrir el selector visual de Google Drive.
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
                <button type="submit" disabled={isBusy || !fileIds.trim()}>
                  {isBusy ? "Importando..." : "Importar"}
                </button>
              </footer>
            </>
          )}
        </form>
      </section>
    </div>
  );
}

function AssignmentWorkflowList({ assignments, mode, onAction, onDownload, pagination }) {
  const isAssigned = mode === "assigned";
  const STATUS_LABELS = {
    PENDING: "Pendiente",
    SIGNED: "Firmado",
    APPROVED: "Aprobado",
    ACCEPTED: "Aprobado",
    REJECTED: "Rechazado",
    VIEWED: "Visto",
    CANCELLED: "Cancelado",
  };

  return (
    <section className="documents-list-section">
      <div className="section-header-row">
        <h3>{isAssigned ? "Documentos asignados a mi" : "Documentos que gestiono"}</h3>
        <span className="section-header-badge">{assignments.length} asignaciones cargadas</span>
      </div>
      <div className="workflow-list">
        {assignments.map((assignment) => (
          <article className="workflow-card" key={assignment.assignmentId}>
            <div>
              <strong>Documento {assignment.documentId.slice(0, 8)}</strong>
              <p style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap", margin: "4px 0" }}>
                <span>Estado:</span>
                <span className={`status-badge status-${assignment.status.toLowerCase()}`}>
                  {STATUS_LABELS[assignment.status] || assignment.status}
                </span>
                {assignment.dueAt ? ` · vence ${formatDate(assignment.dueAt)}` : ""}
              </p>
              <span>
                {isAssigned ? `Asignado por ${assignment.assignedByUserId}` : `Asignado a ${assignment.assignedToUserId}`}
              </span>
            </div>
            <div className="workflow-actions">
              {assignment.allowDownload && (
                <button className="action-button-secondary" type="button" onClick={() => onDownload(assignment)}>
                  Descargar
                </button>
              )}
              {isAssigned && assignment.status === "PENDING" && (
                <>
                  <button className="action-button-secondary" type="button" onClick={() => onAction(assignment, "reject")}>
                    Rechazar
                  </button>
                  <button className="action-button-secondary" type="button" onClick={() => onAction(assignment, "sign")}>
                    Firmar
                  </button>
                  <button className="action-button-primary" type="button" onClick={() => onAction(assignment, "accept")}>
                    Aprobar
                  </button>
                </>
              )}
              {!isAssigned && assignment.status === "PENDING" && (
                <button className="action-button-secondary" type="button" onClick={() => onAction(assignment, "cancel")}>
                  Cancelar
                </button>
              )}
            </div>
          </article>
        ))}
        {!assignments.length && !pagination.loading && (
          <div className="empty-documents">
            {isAssigned ? "No tienes documentos asignados." : "Aun no gestionas asignaciones."}
          </div>
        )}
      </div>
      <WorkflowPagination page={pagination} />
    </section>
  );
}

function WorkflowPagination({ page }) {
  if (page.loading) return <p role="status">Cargando…</p>;
  return <div className="workflow-actions">
    {page.error && <button type="button" className="action-button-secondary" onClick={page.reload}>Reintentar</button>}
    {page.hasMore && <button type="button" className="action-button-secondary" onClick={page.loadMore}>Cargar más</button>}
  </div>;
}

function AssignDocumentModal({ document, form, isOpen, users, onChange, onClose, onSubmit }) {
  if (!isOpen) return null;

  return (
    <div className="move-document-backdrop" role="presentation" onClick={onClose}>
      <section
        className="move-document-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="assign-document-title"
        onClick={(event) => event.stopPropagation()}
      >
        <header>
          <div>
            <p>Asignar documento</p>
            <h3 id="assign-document-title">{document?.filename || "Documento"}</h3>
          </div>
          <button className="icon-action-button" type="button" onClick={onClose} aria-label="Cerrar">
            <X size={17} />
          </button>
        </header>
        <form className="assign-document-form" onSubmit={onSubmit}>
          <label>
            Usuario destino
            <select value={form.userId} onChange={(event) => onChange({ ...form, userId: event.target.value })} required>
              <option value="">Selecciona usuario</option>
              {users.map((user) => (
                <option key={user.id} value={user.id}>
                  {user.username} {user.email ? `- ${user.email}` : ""}
                </option>
              ))}
            </select>
          </label>
          <label>
            Vencimiento
            <input
              type="datetime-local"
              value={form.dueAt}
              onChange={(event) => onChange({ ...form, dueAt: event.target.value })}
            />
          </label>
          <label className="assign-checkbox">
            <input
              type="checkbox"
              checked={form.allowDownload}
              onChange={(event) => onChange({ ...form, allowDownload: event.target.checked })}
            />
            Permitir descarga
          </label>
          <footer>
            <button type="button" onClick={onClose}>
              Cancelar
            </button>
            <button type="submit">Asignar</button>
          </footer>
        </form>
      </section>
    </div>
  );
}

function formatFolderCount(folder) {
  return Number(folder.documentCount || 0);
}

function formatDate(value) {
  try {
    return new Intl.DateTimeFormat("es-CL", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function emptyStateText(activeView, selectedFolder) {
  if (activeView === appRoutes.documentFavorites) return "No tienes documentos favoritos.";
  if (activeView === appRoutes.documentFolders && selectedFolder) return "Esta carpeta no tiene documentos.";
  return "No hay documentos para estos filtros.";
}
