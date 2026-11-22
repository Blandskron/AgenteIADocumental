import {
  CalendarClock,
  Check,
  Code2,
  Download,
  FileText,
  RotateCcw,
  ShieldAlert,
  Square,
  X,
} from "lucide-react";
import { useState } from "react";

import { SafeMarkdown } from "@/features/chat/ui/SafeMarkdown.tsx";
import { Button } from "@/shared/components/Button/Button.tsx";
import type {
  AgentAuditEvent,
  AgentQuotaSnapshot,
  AgentRun,
  AgentRunAnalysis,
} from "../types.ts";

interface AgentRunPanelProps {
  run: AgentRun | null;
  quota?: AgentQuotaSnapshot | null;
  analysis?: AgentRunAnalysis | null;
  auditEvents?: AgentAuditEvent[];
  busy: boolean;
  error: string | null;
  onCancel: (runId: string) => void;
  onRetry?: (runId: string) => void;
  onExport?: (runId: string, format: "markdown" | "csv") => void;
  onExportPdf?: (runId: string) => void;
  onAnalyze?: (runId: string) => void;
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
  analysis,
  auditEvents = [],
  busy,
  error,
  onCancel,
  onRetry,
  onExport,
  onExportPdf,
  onAnalyze,
  onDecision,
  onDismiss,
}: AgentRunPanelProps) {
  const [comment, setComment] = useState("");

  if (!run && !error && !busy) {
    return null;
  }

  return (
    <section
      className="agent-run-panel"
      aria-label="Estado de ejecución del agente"
    >
      <div className="agent-run-header">
        <strong className="agent-run-title">
          {busy && !run
            ? "Ejecutando agente documental..."
            : `Agente · ${run?.status ?? "ERROR"}${run?.provider ? ` (${run.provider})` : ""}`}
        </strong>
        <div className="agent-run-actions">
          {quota && (
            <span className="agent-quota-badge">
              Cuota: {quota.tokens_used}/{quota.tokens_limit} tokens
            </span>
          )}
          {run && run.status === "SUCCEEDED" && onExport && (
            <>
              <Button
                variant="secondary"
                className="ui-button--sm"
                onClick={() => onExport(run.run_id, "markdown")}
              >
                <Download size={12} aria-hidden="true" />
                MD
              </Button>
              <Button
                variant="secondary"
                className="ui-button--sm"
                onClick={() => onExport(run.run_id, "csv")}
              >
                <Download size={12} aria-hidden="true" />
                CSV
              </Button>
              {onExportPdf && (
                <Button
                  variant="secondary"
                  className="ui-button--sm"
                  onClick={() => onExportPdf(run.run_id)}
                >
                  <FileText size={12} aria-hidden="true" />
                  PDF
                </Button>
              )}
              {onAnalyze && (
                <Button
                  variant="secondary"
                  className="ui-button--sm"
                  onClick={() => onAnalyze(run.run_id)}
                >
                  <CalendarClock size={12} aria-hidden="true" />
                  Fechas/Montos
                </Button>
              )}
            </>
          )}
          {run &&
            (run.status === "RUNNING" ||
              run.status === "PENDING" ||
              run.status === "WAITING_APPROVAL") && (
              <Button
                variant="secondary"
                className="ui-button--sm"
                onClick={() => onCancel(run.run_id)}
                disabled={busy}
              >
                <Square size={12} aria-hidden="true" />
                Cancelar
              </Button>
            )}
          {run &&
            (run.status === "CANCELLED" || run.status === "FAILED") &&
            onRetry && (
              <Button
                variant="secondary"
                className="ui-button--sm"
                onClick={() => onRetry(run.run_id)}
                disabled={busy}
              >
                <RotateCcw size={12} aria-hidden="true" />
                Reintentar
              </Button>
            )}
          <Button
            variant="ghost"
            className="ui-button--sm"
            onClick={onDismiss}
            aria-label="Cerrar panel de agente"
          >
            <X size={15} aria-hidden="true" />
          </Button>
        </div>
      </div>

      {error && (
        <p role="alert" className="agent-error-alert">
          {error}
        </p>
      )}

      {run && run.steps.length > 0 && (
        <details>
          <summary className="agent-collapsible-summary">
            Pasos ejecutados ({run.steps.length}) · {run.usage_tokens} tokens
          </summary>
          <ol className="agent-steps-list">
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
          <summary className="agent-collapsible-summary">
            <Code2 size={14} aria-hidden="true" />
            Código auditado en sandbox ({run.code_executions.length})
          </summary>
          {run.code_executions.map((exec, idx) => (
            <div key={idx} className="agent-code-block-wrap">
              <pre className="agent-code-pre">
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

      {analysis && (
        <div
          role="region"
          className="agent-analysis-box"
          aria-label="Análisis determinista de fechas y montos"
        >
          <strong>
            Análisis determinista · {analysis.expirations.total_dates} fechas ·{" "}
            {analysis.facts.amounts.length} montos/porcentajes
            {analysis.risks ? ` · Riesgo: ${analysis.risks.risk_level}` : ""}
          </strong>
          {analysis.risks && analysis.risks.findings.length > 0 && (
            <ul className="agent-compact-list">
              {analysis.risks.findings.slice(0, 4).map((f, idx) => (
                <li key={`${f.code}-${idx}`}>
                  <strong>[{f.severity}]</strong> {f.message}
                </li>
              ))}
            </ul>
          )}
          {analysis.expirations.alerts.length > 0 && (
            <ul className="agent-compact-list">
              {analysis.expirations.alerts.slice(0, 6).map((alert, idx) => (
                <li key={`${alert.document_id}-${alert.date}-${idx}`}>
                  <strong>[{alert.urgency}]</strong> {alert.date} (
                  {alert.days_remaining} días) — {alert.filename} [Fuente{" "}
                  {alert.source_index}]
                </li>
              ))}
            </ul>
          )}
          {analysis.facts.amounts.length > 0 && (
            <div>
              <strong>Montos detectados:</strong>{" "}
              {analysis.facts.amounts
                .slice(0, 8)
                .map((a) => `${a.value} [Fuente ${a.source_index}]`)
                .join(" · ")}
            </div>
          )}
        </div>
      )}

      {auditEvents.length > 0 && (
        <details>
          <summary className="agent-collapsible-summary">
            Auditoría de ejecución ({auditEvents.length} eventos)
          </summary>
          <ul className="agent-compact-list">
            {auditEvents.map((ev) => (
              <li key={ev.audit_id}>
                <code>{ev.event_type}</code> · {ev.created_at}
              </li>
            ))}
          </ul>
        </details>
      )}

      {run?.pending_approval && (
        <div
          role="region"
          className="agent-approval-card"
          aria-label="Aprobación humana requerida"
        >
          <div className="agent-approval-header">
            <ShieldAlert size={16} aria-hidden="true" />
            <strong>
              Aprobación humana requerida: {run.pending_approval.action}
            </strong>
          </div>
          <p className="agent-approval-summary">
            {run.pending_approval.summary}
          </p>
          <input
            type="text"
            className="agent-approval-input"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Comentario opcional de auditoría"
            aria-label="Comentario de aprobación"
          />
          <div className="agent-approval-actions">
            <Button
              variant="primary"
              className="ui-button--sm"
              disabled={busy}
              onClick={() =>
                onDecision(
                  run.run_id,
                  run.pending_approval!.approval_id,
                  "approve",
                  comment,
                )
              }
            >
              <Check size={14} aria-hidden="true" />
              Aprobar
            </Button>
            <Button
              variant="danger"
              className="ui-button--sm"
              disabled={busy}
              onClick={() =>
                onDecision(
                  run.run_id,
                  run.pending_approval!.approval_id,
                  "reject",
                  comment,
                )
              }
            >
              <X size={14} aria-hidden="true" />
              Rechazar
            </Button>
          </div>
        </div>
      )}
    </section>
  );
}
