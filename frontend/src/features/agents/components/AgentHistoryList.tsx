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
    <details className="agent-history-details">
      <summary className="agent-history-summary">
        <History size={14} aria-hidden="true" />
        Historial de ejecuciones del agente ({runs.length})
      </summary>
      <div className="agent-history-filters">
        <input
          type="search"
          className="agent-history-search"
          aria-label="Filtrar historial del agente"
          placeholder="Buscar objetivo..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select
          className="agent-history-status-select"
          aria-label="Filtrar por estado"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="ALL">Todos</option>
          <option value="WAITING_APPROVAL">Pendiente aprobación</option>
          <option value="SUCCEEDED">Completados</option>
          <option value="CANCELLED">Cancelados</option>
        </select>
      </div>
      <ul className="agent-history-list">
        {filteredRuns.slice(0, 8).map((item) => (
          <li key={item.run_id}>
            <button
              type="button"
              onClick={() => onSelectRun(item)}
              className={`agent-history-item-btn ${item.run_id === activeRunId ? "agent-history-item-btn--active" : ""}`.trim()}
            >
              <span className="agent-history-item-goal">
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
