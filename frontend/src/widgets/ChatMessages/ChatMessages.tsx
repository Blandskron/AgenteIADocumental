import type {
  Message as ChatMessage,
  Conversation,
} from "@/entities/conversation/model/types.ts";
import type { useExports } from "@/features/document-export/useExports.ts";
import { brandSymbolUrl } from "@/shared/components/Brand/Brand.tsx";
import {
  ArrowUpRight,
  FileSearch,
  FileText,
  ListChecks,
  Loader2,
} from "lucide-react";
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
          <div className="chat-brand-symbol" aria-hidden="true">
            <img src={brandSymbolUrl} alt="" />
          </div>
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
              <FileText className="prompt-icon" size={18} />
              <span>Resumir un documento</span>
              <ArrowUpRight className="prompt-arrow" size={16} />
            </button>
            <button
              type="button"
              onClick={() =>
                onPrompt?.(
                  "¿Cuáles son los plazos y obligaciones de estos documentos?",
                )
              }
            >
              <ListChecks className="prompt-icon" size={18} />
              <span>Identificar obligaciones</span>
              <ArrowUpRight className="prompt-arrow" size={16} />
            </button>
            <button
              type="button"
              onClick={() =>
                onPrompt?.(
                  "Busca la información relevante e indica sus fuentes.",
                )
              }
            >
              <FileSearch className="prompt-icon" size={18} />
              <span>Consultar con fuentes</span>
              <ArrowUpRight className="prompt-arrow" size={16} />
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
            <img src={brandSymbolUrl} alt="" />
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
