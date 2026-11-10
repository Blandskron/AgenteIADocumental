import type { PageProps } from "@/app/router/useAppRouter.ts";
import type { Message } from "@/entities/conversation/model/types.ts";
import { useSidebarState } from "@/shared/hooks/useSidebarState.ts";
import { X } from "lucide-react";
import { useEffect, useState } from "react";

import { useAuthContext } from "@/app/providers/AuthProvider.tsx";
import { appRoutes } from "@/app/router/routes.ts";
import { useChat } from "@/features/chat/hooks/useChat.ts";
import { useConversations } from "@/features/conversations/hooks/useConversations.ts";
import { ExportHistory } from "@/features/document-export/ExportHistory.tsx";
import { useExports } from "@/features/document-export/useExports.ts";
import { useDocumentUpload } from "@/features/documents/hooks/useDocumentUpload.ts";
import { useTransfers } from "@/features/transfers/hooks/useTransfers.ts";
import { TransferModal } from "@/shared/components/TransferModal/TransferModal.tsx";
import { TransferWarning } from "@/shared/components/TransferModal/TransferWarning.tsx";
import { useScrollToBottom } from "@/shared/hooks/useScrollToBottom.ts";
import { AppShell } from "@/shared/layouts/AppShell.tsx";
import { ChatComposer } from "@/widgets/ChatComposer/ChatComposer.tsx";
import { ChatMessages } from "@/widgets/ChatMessages/ChatMessages.tsx";
import { Sidebar } from "@/widgets/Sidebar/Sidebar.tsx";

export function ChatPage({ onNavigate }: PageProps) {
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
  const [sidebarOpen, setSidebarOpen] = useSidebarState();
  const [transfersOpen, setTransfersOpen] = useState(false);
  const [exportsOpen, setExportsOpen] = useState(false);

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

  const isStarterState =
    !activeConversation?.historyBefore &&
    (!activeConversation?.messages?.length ||
      (activeConversation.messages.length === 1 &&
        activeConversation.messages[0]?.role === "assistant" &&
        activeConversation.messages[0].content?.startsWith(
          "Soy Blandskron Documental.",
        )));
  const latestMessage = activeConversation?.messages?.at(-1);
  const messagesRef = useScrollToBottom({
    conversationId: activeConversation.id,
    message: latestMessage,
    busy: chat.isBusy,
    enabled: !isStarterState,
  });

  useEffect(() => {
    function openTransfers() {
      setTransfersOpen(true);
    }

    window.addEventListener("blandskron:open-transfers", openTransfers);
    return () =>
      window.removeEventListener("blandskron:open-transfers", openTransfers);
  }, []);

  async function handleNewConversation() {
    await createNewConversation();
    chat.resetComposer();
  }

  function handleLogout() {
    chat.resetComposer();
    logout();
  }

  const pdfExports = useExports(
    documentExportClient,
    JSON.stringify([storageScope, activeConversation?.id]),
  );
  useEffect(() => {
    setExportsOpen(false);
  }, [pdfExports.controller]);
  function closeExports() {
    pdfExports.controller.cancelPending();
    setExportsOpen(false);
  }
  function handleExportMessagePdf(message: Message, index: number) {
    if (
      !message?.content ||
      message.role !== "assistant" ||
      !activeConversation
    )
      return;
    const question = [...(activeConversation.messages || [])]
      .slice(0, index)
      .reverse()
      .find((item) => item.role === "user");
    return pdfExports.controller.exportMessage(message.id || `local-${index}`, {
      conversationId: activeConversation.id,
      messageId: message.id,
      title: activeConversation.title || "Respuesta documental",
      question: question?.content || "",
      answer: message.content,
      sources: message.sources || [],
      metadata: { exported_from: "chat", source_message_index: index },
    });
  }
  return (
    <AppShell
      sidebarOpen={sidebarOpen}
      onSidebarChange={setSidebarOpen}
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
      <ExportHistory
        isOpen={exportsOpen}
        onClose={closeExports}
        exports={pdfExports}
      />
      <main
        id="main-content"
        tabIndex={-1}
        className={`chat blandskron-screen ${isStarterState ? "starter-state" : ""}`.trim()}
      >
        <button
          type="button"
          className="export-history-trigger"
          onClick={() => {
            setExportsOpen(true);
            pdfExports.controller.refresh();
          }}
        >
          Mis PDFs
        </button>
        <div className="chat-local-header">
          <h2>{activeConversation?.title || "Conversación"}</h2>
          {activeConversation?.selectedDocuments?.length > 0 && (
            <div
              className="selected-documents-chip"
              style={{ margin: 0, alignSelf: "flex-start" }}
            >
              <span>
                {activeConversation.selectedDocuments
                  .map((doc) => doc.filename)
                  .join(", ")}
              </span>
              <button
                onClick={() => setSelectedDocuments([])}
                aria-label="Quitar documentos seleccionados"
              >
                <X size={13} />
              </button>
            </div>
          )}
        </div>

        <ChatMessages
          onPrompt={chat.setQuestion}
          conversations={conversations}
          messages={activeConversation?.messages || []}
          hasOlderMessages={Boolean(activeConversation?.historyBefore)}
          historyError={historyError}
          historyLoading={historyLoading}
          onLoadOlderMessages={loadOlderMessages}
          onExportMessagePdf={handleExportMessagePdf}
          pdfExportState={pdfExports}
          isBusy={chat.isBusy}
          syncError={syncError}
          messagesRef={messagesRef}
        />
        {pdfExports.busyKey && (
          <button type="button" onClick={pdfExports.controller.cancelPending}>
            Cancelar PDF
          </button>
        )}

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
            chat.setQuestion((prev) => prev + (prev ? " " : "") + transcript)
          }
        />

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
      </main>
    </AppShell>
  );
}
