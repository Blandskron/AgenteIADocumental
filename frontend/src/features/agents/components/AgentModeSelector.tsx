import { Bot, Code2, MessageSquare } from "lucide-react";

import type {
  AgentCapabilities,
  AgentTemplate,
  ChatExecutionMode,
} from "../types.ts";

interface AgentModeSelectorProps {
  mode: ChatExecutionMode;
  capabilities: AgentCapabilities | null;
  templates?: AgentTemplate[];
  selectedTemplateId?: string;
  onModeChange: (mode: ChatExecutionMode) => void;
  onTemplateChange?: (templateId: string) => void;
}

export function AgentModeSelector({
  mode,
  capabilities,
  templates = [],
  selectedTemplateId = "research_general",
  onModeChange,
  onTemplateChange,
}: AgentModeSelectorProps) {
  if (!capabilities?.agents_enabled) {
    return null;
  }

  return (
    <div
      className="agent-mode-selector"
      role="group"
      aria-label="Modo de ejecución"
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "0.35rem",
        padding: "0.2rem",
        borderRadius: "999px",
        background: "var(--surface-muted, rgba(127,127,127,0.12))",
      }}
    >
      <button
        type="button"
        aria-pressed={mode === "chat"}
        onClick={() => onModeChange("chat")}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "0.3rem",
          padding: "0.25rem 0.65rem",
          borderRadius: "999px",
          border: "none",
          cursor: "pointer",
          fontSize: "0.8rem",
          fontWeight: mode === "chat" ? 600 : 400,
          background:
            mode === "chat" ? "var(--surface-primary, #fff)" : "transparent",
          color: "inherit",
        }}
      >
        <MessageSquare size={14} aria-hidden="true" />
        Chat
      </button>
      <button
        type="button"
        aria-pressed={mode === "agent"}
        onClick={() => onModeChange("agent")}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "0.3rem",
          padding: "0.25rem 0.65rem",
          borderRadius: "999px",
          border: "none",
          cursor: "pointer",
          fontSize: "0.8rem",
          fontWeight: mode === "agent" ? 600 : 400,
          background:
            mode === "agent" ? "var(--surface-primary, #fff)" : "transparent",
          color: "inherit",
        }}
      >
        <Bot size={14} aria-hidden="true" />
        Agente
      </button>
      {capabilities.code_mode_enabled && (
        <button
          type="button"
          aria-pressed={mode === "code_mode"}
          onClick={() => onModeChange("code_mode")}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "0.3rem",
            padding: "0.25rem 0.65rem",
            borderRadius: "999px",
            border: "none",
            cursor: "pointer",
            fontSize: "0.8rem",
            fontWeight: mode === "code_mode" ? 600 : 400,
            background:
              mode === "code_mode"
                ? "var(--surface-primary, #fff)"
                : "transparent",
            color: "inherit",
          }}
        >
          <Code2 size={14} aria-hidden="true" />
          Code Mode
        </button>
      )}
      {mode !== "chat" && templates.length > 0 && onTemplateChange && (
        <select
          aria-label="Plantilla de agente"
          value={selectedTemplateId}
          onChange={(e) => onTemplateChange(e.target.value)}
          style={{
            marginLeft: "0.25rem",
            padding: "0.2rem 0.45rem",
            borderRadius: "999px",
            border: "1px solid var(--border-subtle, rgba(127,127,127,0.3))",
            background: "var(--surface-primary, #fff)",
            color: "inherit",
            fontSize: "0.78rem",
          }}
        >
          {templates.map((tpl) => (
            <option key={tpl.template_id} value={tpl.template_id}>
              {tpl.title}
            </option>
          ))}
        </select>
      )}
    </div>
  );
}
