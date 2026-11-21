import type { Message as ChatMessage } from "@/entities/conversation/model/types.ts";
import { brandSymbolUrl } from "@/shared/components/Brand/Brand.tsx";
import { FileDown, Loader2, MessageSquare } from "lucide-react";
import { useState } from "react";

import { SafeMarkdown } from "./SafeMarkdown";
import { SourceList } from "./SourceList";

export function Message({
  isExportingPdf = false,
  exportDisabled = false,
  message,
  onExportPdf,
}: {
  isExportingPdf?: boolean;
  exportDisabled?: boolean;
  message: ChatMessage;
  onExportPdf?: () => void;
}) {
  const isAssistant = message.role === "assistant";
  const [activeSourceIndex, setActiveSourceIndex] = useState<number | null>(
    null,
  );

  return (
    <article className={`message ${message.role}`}>
      <div className="avatar" aria-hidden="true">
        {isAssistant ? (
          <img src={brandSymbolUrl} alt="" />
        ) : (
          <MessageSquare size={18} />
        )}
      </div>
      <div className="bubble">
        <div className="message-meta">
          {isAssistant ? "Blandskron Documental" : "Tu"}
        </div>
        <div className="message-text">
          {isAssistant ? (
            <SafeMarkdown
              content={message.content}
              sourceCount={message.sources?.length || 0}
              onCitationClick={(index) => setActiveSourceIndex(index)}
            />
          ) : (
            message.content
          )}
        </div>
        {isAssistant && onExportPdf && (
          <div className="message-actions">
            <button
              className="message-export-button"
              type="button"
              onClick={onExportPdf}
              disabled={isExportingPdf || exportDisabled}
              title="Exportar respuesta como PDF"
            >
              {isExportingPdf ? <Loader2 size={15} /> : <FileDown size={15} />}
              PDF
            </button>
          </div>
        )}
        <SourceList
          sources={message.sources}
          activeSourceIndex={activeSourceIndex}
          onSelectSource={setActiveSourceIndex}
        />
      </div>
    </article>
  );
}
