import { Check, Code2, Download, ShieldAlert, Square, X } from "lucide-react";
import { useState } from "react";

import { SafeMarkdown } from "@/features/chat/ui/SafeMarkdown.tsx";
import type { AgentQuotaSnapshot, AgentRun } from "../types.ts";

interface AgentRunPanelProps {
  run: AgentRun | null;
  quota?: AgentQuotaSnapshot | null;
  busy: boolean;
  error: string | null;
  onCancel: (runId: string) => void;
  onExport?: (runId: string, format: "markdown" | "csv") => void;
  onDecision: (
    runId: string,
    approvalId: string,
    decision: "approve" | "reject",
    comment: string,
  ) => void;
  onDismiss: () => void;
}

export function AgentRunPanel({
  run,
  quota,
  busy,
  error,
  onCancel,
  onExport,
  onDecision,
  onDismiss,
}: AgentRunPanelProps) {
  const [comment, setComment] = useState("");

  if (!run && !error && !busy) {
    return null;
  }

  return (
    <section
      aria-label="Estado de ejecución del agente"
      style={{
        margin: "0.5rem 1rem",
        padding: "0.9rem 1rem",
        borderRadius: "12px",
        border: "1px solid var(--border-subtle, rgba(127,127,127,0.25))",
        background: "var(--surface-elevated, rgba(127,127,127,0.06))",
        display: "flex",
        flexDirection: "column",
        gap: "0.7rem",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "0.5rem",
        }}
      >
        <strong style={{ fontSize: "0.9rem" }}>
          {busy && !run
            ? "Ejecutando agente documental..."
            : `Agente · ${run?.status ?? "ERROR"}${run?.provider ? ` (${run.provider})` : ""}`}
        </strong>
        <div style={{ display: "flex", gap: "0.4rem", alignItems: "center" }}>
          {quota && (
            <span
              style={{
                fontSize: "0.75rem",
                opacity: 0.75,
                marginRight: "0.25rem",
              }}
            >
              Cuota: {quota.tokens_used}/{quota.tokens_limit} tokens
            </span>
          )}
          {run && run.status === "SUCCEEDED" && onExport && (
            <>
              <button
                type="button"
                onClick={() => onExport(run.run_id, "markdown")}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.25rem",
                  padding: "0.2rem 0.5rem",
                  borderRadius: "8px",
                  border: "1px solid currentColor",
                  background: "transparent",
                  cursor: "pointer",
                  fontSize: "0.75rem",
                }}
              >
                <Download size={12} aria-hidden="true" />
                MD
              </button>
              <button
                type="button"
                onClick={() => onExport(run.run_id, "csv")}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.25rem",
                  padding: "0.2rem 0.5rem",
                  borderRadius: "8px",
                  border: "1px solid currentColor",
                  background: "transparent",
                  cursor: "pointer",
                  fontSize: "0.75rem",
                }}
              >
                <Download size={12} aria-hidden="true" />
                CSV
              </button>
            </>
          )}
          {run &&
            (run.status === "RUNNING" ||
              run.status === "PENDING" ||
              run.status === "WAITING_APPROVAL") && (
              <button
                type="button"
                onClick={() => onCancel(run.run_id)}
                disabled={busy}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.3rem",
                  padding: "0.25rem 0.6rem",
                  borderRadius: "8px",
                  border: "1px solid currentColor",
                  background: "transparent",
                  cursor: "pointer",
                  fontSize: "0.8rem",
                }}
              >
                <Square size={12} aria-hidden="true" />
                Cancelar
              </button>
            )}
          <button
            type="button"
            onClick={onDismiss}
            aria-label="Cerrar panel de agente"
            style={{
              background: "transparent",
              border: "none",
              cursor: "pointer",
              color: "inherit",
            }}
          >
            <X size={15} aria-hidden="true" />
          </button>
        </div>
      </div>

      {error && (
        <p
          role="alert"
          style={{ margin: 0, color: "#dc2626", fontSize: "0.85rem" }}
        >
          {error}
        </p>
      )}

      {run && run.steps.length > 0 && (
        <details>
          <summary style={{ cursor: "pointer", fontSize: "0.83rem" }}>
            Pasos ejecutados ({run.steps.length}) · {run.usage_tokens} tokens
          </summary>
          <ol
            style={{
              margin: "0.4rem 0 0 1.2rem",
              padding: 0,
              fontSize: "0.8rem",
            }}
          >
            {run.steps.map((step) => (
              <li key={`${step.index}-${step.tool}`}>
                <code>{step.tool}</code> — {step.status} ({step.duration_ms} ms)
              </li>
            ))}
          </ol>
        </details>
      )}

      {run?.code_executions && run.code_executions.length > 0 && (
        <details>
          <summary
            style={{
              cursor: "pointer",
              fontSize: "0.83rem",
              display: "inline-flex",
              alignItems: "center",
              gap: "0.3rem",
            }}
          >
            <Code2 size={14} aria-hidden="true" />
            Código auditado en sandbox ({run.code_executions.length})
          </summary>
          {run.code_executions.map((exec, idx) => (
            <div key={idx} style={{ marginTop: "0.4rem" }}>
              <pre
                style={{
                  margin: 0,
                  padding: "0.6rem",
                  borderRadius: "8px",
                  overflowX: "auto",
                  fontSize: "0.78rem",
                  background: "rgba(0,0,0,0.08)",
                }}
              >
                <code>{exec.code}</code>
              </pre>
            </div>
          ))}
        </details>
      )}

      {run?.result_markdown && (
        <div>
          <SafeMarkdown
            content={run.result_markdown}
            sourceCount={run.sources.length}
          />
        </div>
      )}

      {run?.pending_approval && (
        <div
          role="region"
          aria-label="Aprobación humana requerida"
          style={{
            padding: "0.75rem",
            borderRadius: "10px",
            border: "1px solid #d97706",
            background: "rgba(217, 119, 6, 0.08)",
            display: "flex",
            flexDirection: "column",
            gap: "0.5rem",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
            <ShieldAlert size={16} aria-hidden="true" />
            <strong style={{ fontSize: "0.85rem" }}>
              Aprobación humana requerida: {run.pending_approval.action}
            </strong>
          </div>
          <p style={{ margin: 0, fontSize: "0.83rem" }}>
            {run.pending_approval.summary}
          </p>
          <input
            type="text"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Comentario opcional de auditoría"
            aria-label="Comentario de aprobación"
            style={{
              padding: "0.4rem 0.6rem",
              borderRadius: "6px",
              border: "1px solid var(--border-subtle, rgba(127,127,127,0.35))",
              fontSize: "0.82rem",
            }}
          />
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                onDecision(
                  run.run_id,
                  run.pending_approval!.approval_id,
                  "approve",
                  comment,
                )
              }
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.3rem",
                padding: "0.35rem 0.75rem",
                borderRadius: "8px",
                border: "none",
                background: "#16a34a",
                color: "#fff",
                cursor: "pointer",
                fontSize: "0.82rem",
              }}
            >
              <Check size={14} aria-hidden="true" />
              Aprobar
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                onDecision(
                  run.run_id,
                  run.pending_approval!.approval_id,
                  "reject",
                  comment,
                )
              }
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.3rem",
                padding: "0.35rem 0.75rem",
                borderRadius: "8px",
                border: "1px solid #dc2626",
                background: "transparent",
                color: "#dc2626",
                cursor: "pointer",
                fontSize: "0.82rem",
              }}
            >
              <X size={14} aria-hidden="true" />
              Rechazar
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
