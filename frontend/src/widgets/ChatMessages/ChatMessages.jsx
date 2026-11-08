import { Globe2, Image, Loader2, Pencil } from "lucide-react";
const iaIconUrl = "/blandskron.svg";

import { Message } from "../../features/chat/ui/Message";

export function ChatMessages({
  conversations = [],
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
}) {
  const isStarterState = !hasOlderMessages && (
    messages.length === 0 ||
    (messages.length === 1 &&
      messages[0].role === "assistant" &&
      messages[0].content?.startsWith("Soy Blandskron Documental."))
  );

  return (
    <section className="messages" ref={messagesRef}>
      {syncError && (
        <p className="message-export-status error" role="alert">
          No se pudo sincronizar el historial con el servidor.
        </p>
      )}
      {hasOlderMessages && (
        <div className="message-history-controls">
          <button type="button" disabled={historyLoading} onClick={onLoadOlderMessages}>
            {historyLoading ? "Cargando mensajes…" : "Cargar mensajes anteriores"}
          </button>
          {historyError && <p role="alert">{historyError}</p>}
        </div>
      )}
      {isStarterState && (
        <div className="blandskron-home-grid">
          <h1>¿Cuál es el programa de hoy?</h1>
          <div className="blandskron-prompt-actions">
            <button type="button"><Image size={16} /> Crea una imagen</button>
            <button type="button"><Pencil size={16} /> Escribe o edita</button>
            <button type="button"><Globe2 size={16} /> Busca información</button>
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

      {!isStarterState && (pdfExportState?.error || pdfExportState?.success) && (
        <div role={pdfExportState.error ? "alert" : "status"} className={`message-export-status ${pdfExportState.error ? "error" : "success"}`}>
          {pdfExportState.error || pdfExportState.success}
        </div>
      )}

      {isBusy && (
        <article className="message assistant">
          <div className="avatar" aria-hidden="true">
            <img src={iaIconUrl} alt="" />
          </div>
          <div className="bubble typing">
            <Loader2 size={18} />
            Procesando...
          </div>
        </article>
      )}
    </section>
  );
}
