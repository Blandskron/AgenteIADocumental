import { Bot, Code2, MessageSquare } from "lucide-react";

import type { AgentCapabilities, ChatExecutionMode } from "../types.ts";

interface AgentModeSelectorProps {
  mode: ChatExecutionMode;
  capabilities: AgentCapabilities | null;
  onModeChange: (mode: ChatExecutionMode) => void;
}

export function AgentModeSelector({
  mode,
  capabilities,
  onModeChange,
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
    </div>
  );
}
