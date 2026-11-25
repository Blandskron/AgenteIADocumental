import type { Message as ChatMessage } from "@/entities/conversation/model/types.ts";
import { Badge } from "@/shared/components/Badge/Badge.tsx";
import { brandSymbolUrl } from "@/shared/components/Brand/Brand.tsx";
import {
  BookOpen,
  FileDown,
  Loader2,
  MessageSquare,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
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
  const [editorialReading, setEditorialReading] = useState(false);
  const sourceCount = message.sources?.length || 0;

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
        <div className="message-meta-row">
          <div className="message-meta">{isAssistant ? "KronDocs" : "Tú"}</div>
          {isAssistant && (
            <Badge
              variant="ai"
              icon={<Sparkles size={11} aria-hidden="true" />}
            >
              IA Documental
            </Badge>
          )}
          {isAssistant && sourceCount > 0 && (
            <Badge
              variant="verified"
              icon={<ShieldCheck size={11} aria-hidden="true" />}
            >
              {sourceCount} {sourceCount === 1 ? "fuente" : "fuentes"}
            </Badge>
          )}
        </div>
        <div
          className={`message-text ${isAssistant && editorialReading ? "reading-mode-serif" : ""}`.trim()}
        >
          {isAssistant ? (
            <SafeMarkdown
              content={message.content}
              sourceCount={sourceCount}
              onCitationClick={(index) => setActiveSourceIndex(index)}
            />
          ) : (
            message.content
          )}
        </div>
        {isAssistant && (
          <div className="message-actions">
            <button
              className={`message-export-button ${editorialReading ? "is-active" : ""}`.trim()}
              type="button"
              aria-pressed={editorialReading}
              onClick={() => setEditorialReading((prev) => !prev)}
              title="Alternar tipografía editorial de lectura extensa"
            >
              <BookOpen size={15} aria-hidden="true" />
              Lectura
            </button>
            {onExportPdf && (
              <button
                className="message-export-button"
                type="button"
                onClick={onExportPdf}
                disabled={isExportingPdf || exportDisabled}
                title="Exportar respuesta como PDF"
              >
                {isExportingPdf ? (
                  <Loader2 size={15} aria-hidden="true" />
                ) : (
                  <FileDown size={15} aria-hidden="true" />
                )}
                PDF
              </button>
            )}
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
