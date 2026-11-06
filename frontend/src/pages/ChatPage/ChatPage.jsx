import { useEffect, useState } from "react";
import { X } from "lucide-react";

import { useAuthContext } from "../../app/providers/AuthProvider";
import { appRoutes } from "../../app/router/routes";
import { AppShell } from "../../shared/layouts/AppShell";
import { TransferModal } from "../../shared/components/TransferModal/TransferModal";
import { useScrollToBottom } from "../../shared/hooks/useScrollToBottom";
import { useChat } from "../../features/chat/hooks/useChat";
import { useConversations } from "../../features/conversations/hooks/useConversations";
import { createChatMessagePdf, downloadExport } from "../../features/document-export/api/document-export.api";
import { useDocumentUpload } from "../../features/documents/hooks/useDocumentUpload";
import { useTransfers } from "../../features/transfers/hooks/useTransfers";
import { ChatComposer } from "../../widgets/ChatComposer/ChatComposer";
import { ChatMessages } from "../../widgets/ChatMessages/ChatMessages";
import { Sidebar } from "../../widgets/Sidebar/Sidebar";

export function ChatPage({ onNavigate }) {
  const {
    chatClient,
    conversationClient,
    currentUser,
    documentClient,
    documentExportClient,
    documentTransferClient,
    logout,
    storageScope,
  } = useAuthContext();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [transfersOpen, setTransfersOpen] = useState(false);
  const [pdfExportState, setPdfExportState] = useState({ messageKey: "", error: "", success: "" });

  const transfers = useTransfers(documentTransferClient);
  const conversationsState = useConversations(storageScope, conversationClient);
  const {
    activeConversation,
    conversations,
    setActiveId,
    addMessage,
    createNewConversation,
    deleteConversation,
    historyError,
    historyLoading,
    loadOlderMessages,
    setSelectedDocuments,
    syncError,
  } = conversationsState;

  const documentUpload = useDocumentUpload();
  const chat = useChat({
    chatClient,
    documentClient,
    activeConversation,
    addMessage,
    setSelectedDocuments,
    selectedFile: documentUpload.selectedFile,
    clearSelectedFile: documentUpload.clearSelectedFile,
    transfers,
  });

  const isStarterState = !activeConversation?.historyBefore && (
    !activeConversation?.messages?.length ||
    (activeConversation.messages.length === 1 &&
      activeConversation.messages[0]?.role === "assistant" &&
      activeConversation.messages[0].content?.startsWith("Soy Blandskron Documental."))
  );
  const latestMessage = activeConversation?.messages?.at(-1);
  const messagesRef = useScrollToBottom([activeConversation?.id, latestMessage, chat.isBusy], { enabled: !isStarterState });

  useEffect(() => {
    function openTransfers() {
      setTransfersOpen(true);
    }

    window.addEventListener("blandskron:open-transfers", openTransfers);
    return () => window.removeEventListener("blandskron:open-transfers", openTransfers);
  }, []);

  async function handleNewConversation() {
    await createNewConversation();
    chat.resetComposer();
  }

  function handleLogout() {
    chat.resetComposer();
    logout();
  }

  async function handleExportMessagePdf(message, index) {
    if (!message?.content || message.role !== "assistant" || pdfExportState.messageKey || !activeConversation) return;

    const messageKey = message.id || `local-${index}`;
    const previousUserMessage = [...(activeConversation.messages || [])]
      .slice(0, index)
      .reverse()
      .find((item) => item.role === "user");

    setPdfExportState({ messageKey, error: "", success: "" });

    try {
      const exported = await createChatMessagePdf(documentExportClient, {
        conversationId: activeConversation.id,
        messageId: message.id,
        title: activeConversation.title || "Respuesta documental",
        question: previousUserMessage?.content || "",
        answer: message.content,
        sources: message.sources || [],
        metadata: {
          exported_from: "chat",
          source_message_index: index,
        },
      });
      const file = await downloadExport(documentExportClient, exported.exportId);
      const url = URL.createObjectURL(file.blob);
      const link = document.createElement("a");

      link.href = url;
      link.download = exported.filename || readFilename(file.contentDisposition) || "respuesta-documental.pdf";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setPdfExportState({ messageKey: "", error: "", success: "PDF generado correctamente." });
    } catch (error) {
      setPdfExportState({
        messageKey: "",
        error: error?.message || "No se pudo generar el PDF.",
        success: "",
      });
    }
  }

  return (
    <AppShell
      sidebarOpen={sidebarOpen}
      sidebar={
        <Sidebar
          collapsed={!sidebarOpen}
          conversations={conversations}
          activeConversation={activeConversation}
          onClose={() => setSidebarOpen(false)}
          onOpen={() => setSidebarOpen(true)}
          onCreateConversation={handleNewConversation}
          onDeleteConversation={deleteConversation}
          onLogout={handleLogout}
          onNavigate={onNavigate}
          onSelectConversation={setActiveId}
          activeRoute={appRoutes.chat}
          user={currentUser}
        />
      }
    >
      <main className={`chat blandskron-screen ${isStarterState ? "starter-state" : ""}`.trim()}>
        <div className="chat-local-header">
          <h2>
            {activeConversation?.title || "Conversación"}
          </h2>
          {activeConversation?.selectedDocuments?.length > 0 && (
            <div className="selected-documents-chip" style={{ margin: 0, alignSelf: "flex-start" }}>
              <span>{activeConversation.selectedDocuments.map((doc) => doc.filename).join(", ")}</span>
              <button onClick={() => setSelectedDocuments([])} aria-label="Quitar documentos seleccionados">
                <X size={13} />
              </button>
            </div>
          )}
        </div>

        <ChatMessages
          conversations={conversations}
          messages={activeConversation?.messages || []}
          hasOlderMessages={Boolean(activeConversation?.historyBefore)}
          historyError={historyError}
          historyLoading={historyLoading}
          onLoadOlderMessages={loadOlderMessages}
          onExportMessagePdf={handleExportMessagePdf}
          pdfExportState={pdfExportState}
          isBusy={chat.isBusy}
          syncError={syncError}
          messagesRef={messagesRef}
        />

        <ChatComposer
          fileInputRef={documentUpload.fileInputRef}
          isBusy={chat.isBusy}
          onClearFile={documentUpload.clearSelectedFile}
          onFileChange={documentUpload.handleFileChange}
          onOpenFilePicker={documentUpload.openFilePicker}
          onQuestionChange={chat.setQuestion}
          onSubmit={chat.submit}
          onUploadOnly={chat.uploadOnly}
          question={chat.question}
          selectedFile={documentUpload.selectedFile}
          isStarterState={isStarterState}
          onDictate={(transcript) =>
            chat.setQuestion(
              (prev) => prev + (prev ? " " : "") + transcript
            )
          }
        />

        <TransferModal
          error={transfers.error}
          isLoading={transfers.isLoading}
          isOpen={transfersOpen}
          onClearHistory={transfers.clearHistory}
          onClose={() => setTransfersOpen(false)}
          transfers={transfers.transfers}
        />
      </main>
    </AppShell>
  );
}

function readFilename(contentDisposition = "") {
  const match = contentDisposition.match(/filename="?([^";]+)"?/i);
  return match?.[1] || "";
}
