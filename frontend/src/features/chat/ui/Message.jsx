import { FileDown, Loader2, MessageSquare } from "lucide-react";
const iaIconUrl = "/blandskron.svg";

import { SourceList } from "./SourceList";

export function Message({ isExportingPdf = false, message, onExportPdf }) {
  const isAssistant = message.role === "assistant";

  return (
    <article className={`message ${message.role}`}>
      <div className="avatar" aria-hidden="true">
        {isAssistant ? <img src={iaIconUrl} alt="" /> : <MessageSquare size={18} />}
      </div>
      <div className="bubble">
        <div className="message-meta">{isAssistant ? "Blandskron Documental" : "Tu"}</div>
        <div className="message-text">{message.content}</div>
        {isAssistant && onExportPdf && (
          <div className="message-actions">
            <button
              className="message-export-button"
              type="button"
              onClick={onExportPdf}
              disabled={isExportingPdf}
              title="Exportar respuesta como PDF"
            >
              {isExportingPdf ? <Loader2 size={15} /> : <FileDown size={15} />}
              PDF
            </button>
          </div>
        )}
        <SourceList sources={message.sources} />
      </div>
    </article>
  );
}
