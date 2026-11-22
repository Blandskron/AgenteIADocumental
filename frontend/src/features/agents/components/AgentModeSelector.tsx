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
    >
      <button
        type="button"
        className="agent-mode-pill"
        aria-pressed={mode === "chat"}
        onClick={() => onModeChange("chat")}
      >
        <MessageSquare size={14} aria-hidden="true" />
        Chat
      </button>
      <button
        type="button"
        className="agent-mode-pill"
        aria-pressed={mode === "agent"}
        onClick={() => onModeChange("agent")}
      >
        <Bot size={14} aria-hidden="true" />
        Agente
      </button>
      {capabilities.code_mode_enabled && (
        <button
          type="button"
          className="agent-mode-pill"
          aria-pressed={mode === "code_mode"}
          onClick={() => onModeChange("code_mode")}
        >
          <Code2 size={14} aria-hidden="true" />
          Code Mode
        </button>
      )}
      {mode !== "chat" && templates.length > 0 && onTemplateChange && (
        <select
          className="agent-template-select"
          aria-label="Plantilla de agente"
          value={selectedTemplateId}
          onChange={(e) => onTemplateChange(e.target.value)}
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
