import type {
  Message as ChatMessage,
  Conversation,
} from "@/entities/conversation/model/types.ts";
import type { useExports } from "@/features/document-export/useExports.ts";
import { FileSearch, FileText, ListChecks, Loader2 } from "lucide-react";
import type { RefObject } from "react";
interface ChatMessagesProps {
  conversations?: Conversation[];
  hasOlderMessages?: boolean;
  historyError?: string;
  historyLoading?: boolean;
  isBusy: boolean;
  messages: ChatMessage[];
  messagesRef: RefObject<HTMLElement | null>;
  onExportMessagePdf?: (message: ChatMessage, index: number) => void;
  onLoadOlderMessages?: () => void;
  pdfExportState?: ReturnType<typeof useExports>;
  syncError?: string;
  onPrompt?: (prompt: string) => void;
}
const iaIconUrl = "/blandskron.svg";

import { Message } from "@/features/chat/ui/Message.tsx";

export function ChatMessages({
  hasOlderMessages,
  historyError,
  historyLoading,
  isBusy,
  messages,
  messagesRef,
  onExportMessagePdf,
  onLoadOlderMessages,
  pdfExportState,
  syncError,
  onPrompt,
}: ChatMessagesProps) {
  const isStarterState =
    !hasOlderMessages &&
    (messages.length === 0 ||
      (messages.length === 1 &&
        messages[0].role === "assistant" &&
        messages[0].content?.startsWith("Soy Blandskron Documental.")));

  return (
    <section
      aria-label="Conversación documental"
      className="messages"
      ref={messagesRef}
    >
      {syncError && (
        <p className="message-export-status error" role="alert">
          No se pudo sincronizar el historial con el servidor.
        </p>
      )}
      {hasOlderMessages && (
        <div className="message-history-controls">
          <button
            type="button"
            disabled={historyLoading}
            onClick={onLoadOlderMessages}
          >
            {historyLoading
              ? "Cargando mensajes…"
              : "Cargar mensajes anteriores"}
          </button>
          {historyError && <p role="alert">{historyError}</p>}
        </div>
      )}
      {isStarterState && (
        <div className="blandskron-home-grid">
          <h1>Tus documentos, con respuestas claras</h1>
          <p className="starter-description">
            Consulta tu biblioteca o adjunta un archivo. Cada respuesta se apoya
            en tus documentos.
          </p>
          <div className="blandskron-prompt-actions">
            <button
              type="button"
              onClick={() =>
                onPrompt?.("Resume los puntos principales de mis documentos.")
              }
            >
              <FileText size={18} /> Resumir un documento
            </button>
            <button
              type="button"
              onClick={() =>
                onPrompt?.(
                  "¿Cuáles son los plazos y obligaciones de estos documentos?",
                )
              }
            >
              <ListChecks size={18} /> Identificar obligaciones
            </button>
            <button
              type="button"
              onClick={() =>
                onPrompt?.(
                  "Busca la información relevante e indica sus fuentes.",
                )
              }
            >
              <FileSearch size={18} /> Consultar con fuentes
            </button>
          </div>
        </div>
      )}
      {!isStarterState &&
        messages.map((message, index) => {
          const messageKey = message.id || `local-${index}`;
          return (
            <Message
              key={`${message.role}-${messageKey}`}
              message={message}
              onExportPdf={() => onExportMessagePdf?.(message, index)}
              isExportingPdf={pdfExportState?.messageKey === messageKey}
              exportDisabled={Boolean(pdfExportState?.busyKey)}
            />
          );
        })}

      {!isStarterState &&
        (pdfExportState?.error || pdfExportState?.success) && (
          <div
            role={pdfExportState.error ? "alert" : "status"}
            className={`message-export-status ${pdfExportState.error ? "error" : "success"}`}
          >
            {pdfExportState.error || pdfExportState.success}
          </div>
        )}

      {isBusy && (
        <article className="message assistant">
          <div className="avatar" aria-hidden="true">
            <img src={iaIconUrl} alt="" />
          </div>
          <div className="bubble typing" role="status">
            <Loader2 size={18} />
            Procesando...
          </div>
        </article>
      )}
    </section>
  );
}
