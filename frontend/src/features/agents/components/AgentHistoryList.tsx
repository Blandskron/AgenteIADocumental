import { History } from "lucide-react";
import { useState } from "react";

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
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [query, setQuery] = useState("");

  if (!runs.length) {
    return null;
  }

  const normalizedQuery = query.trim().toLowerCase();
  const filteredRuns = runs.filter((item) => {
    if (statusFilter !== "ALL" && item.status !== statusFilter) {
      return false;
    }
    if (
      normalizedQuery &&
      !(item.goal || item.run_id).toLowerCase().includes(normalizedQuery)
    ) {
      return false;
    }
    return true;
  });

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
      <div
        style={{
          display: "flex",
          gap: "0.4rem",
          marginTop: "0.4rem",
          flexWrap: "wrap",
        }}
      >
        <input
          type="search"
          aria-label="Filtrar historial del agente"
          placeholder="Buscar objetivo..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{
            flex: "1 1 160px",
            padding: "0.25rem 0.5rem",
            borderRadius: "6px",
            border: "1px solid var(--border-subtle, rgba(127,127,127,0.3))",
            fontSize: "0.78rem",
          }}
        />
        <select
          aria-label="Filtrar por estado"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          style={{
            padding: "0.25rem 0.45rem",
            borderRadius: "6px",
            border: "1px solid var(--border-subtle, rgba(127,127,127,0.3))",
            fontSize: "0.78rem",
          }}
        >
          <option value="ALL">Todos</option>
          <option value="WAITING_APPROVAL">Pendiente aprobación</option>
          <option value="SUCCEEDED">Completados</option>
          <option value="CANCELLED">Cancelados</option>
        </select>
      </div>
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
        {filteredRuns.slice(0, 8).map((item) => (
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
                {item.goal || item.run_id}
              </span>
              <strong>{item.status}</strong>
            </button>
          </li>
        ))}
      </ul>
    </details>
  );
}
