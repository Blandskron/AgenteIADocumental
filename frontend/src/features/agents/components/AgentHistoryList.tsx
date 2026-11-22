import { History } from "lucide-react";

import type { AgentRun } from "../types.ts";

interface AgentHistoryListProps {
  runs: AgentRun[];
  activeRunId: string | null;
  onSelectRun: (run: AgentRun) => void;
}

export function AgentHistoryList({
  runs,
  activeRunId,
  onSelectRun,
}: AgentHistoryListProps) {
  if (!runs.length) {
    return null;
  }

  return (
    <details
      style={{
        margin: "0 1rem 0.25rem",
        fontSize: "0.8rem",
      }}
    >
      <summary
        style={{
          cursor: "pointer",
          display: "inline-flex",
          alignItems: "center",
          gap: "0.35rem",
        }}
      >
        <History size={14} aria-hidden="true" />
        Historial de ejecuciones del agente ({runs.length})
      </summary>
      <ul
        style={{
          listStyle: "none",
          margin: "0.35rem 0 0",
          padding: 0,
          display: "flex",
          flexDirection: "column",
          gap: "0.25rem",
        }}
      >
        {runs.slice(0, 8).map((item) => (
          <li key={item.run_id}>
            <button
              type="button"
              onClick={() => onSelectRun(item)}
              style={{
                width: "100%",
                textAlign: "left",
                padding: "0.35rem 0.55rem",
                borderRadius: "8px",
                border:
                  item.run_id === activeRunId
                    ? "1px solid currentColor"
                    : "1px solid transparent",
                background: "var(--surface-muted, rgba(127,127,127,0.08))",
                cursor: "pointer",
                color: "inherit",
                fontSize: "0.78rem",
                display: "flex",
                justifyContent: "space-between",
                gap: "0.5rem",
              }}
            >
              <span
                style={{
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {item.goal}
              </span>
              <strong>{item.status}</strong>
            </button>
          </li>
        ))}
      </ul>
    </details>
  );
}
