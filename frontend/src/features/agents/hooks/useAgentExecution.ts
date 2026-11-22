import {
  analyzeAgentRun,
  cancelAgentRun,
  exportAgentRunContent,
  exportAgentRunPdf,
  getAgentHealth,
  getAgentQuota,
  listAgentRunAudit,
  listAgentRuns,
  listAgentTemplates,
  resumeAgentApproval,
  retryAgentRun,
  startAgentRun,
} from "@/features/agents/api/agents.api.ts";
import type {
  AgentAuditEvent,
  AgentCapabilities,
  AgentQuotaSnapshot,
  AgentRun,
  AgentRunAnalysis,
  AgentTemplate,
  ChatExecutionMode,
} from "@/features/agents/types.ts";
import type { MaybeClient } from "@/shared/api/types.ts";
import { useEffect, useState } from "react";

export function useAgentExecution(agentClient: MaybeClient) {
  const [agentCapabilities, setAgentCapabilities] =
    useState<AgentCapabilities | null>(null);
  const [agentTemplates, setAgentTemplates] = useState<AgentTemplate[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] =
    useState<string>("research_general");
  const [agentRuns, setAgentRuns] = useState<AgentRun[]>([]);
  const [agentQuota, setAgentQuota] = useState<AgentQuotaSnapshot | null>(null);
  const [executionMode, setExecutionMode] = useState<ChatExecutionMode>("chat");
  const [activeAgentRun, setActiveAgentRun] = useState<AgentRun | null>(null);
  const [agentAnalysis, setAgentAnalysis] = useState<AgentRunAnalysis | null>(
    null,
  );
  const [agentAuditEvents, setAgentAuditEvents] = useState<AgentAuditEvent[]>(
    [],
  );
  const [agentBusy, setAgentBusy] = useState(false);
  const [agentError, setAgentError] = useState<string | null>(null);

  useEffect(() => {
    if (!agentClient) return;
    const controller = new AbortController();
    const { signal } = controller;

    getAgentHealth(agentClient, { signal })
      .then((caps) => {
        if (signal.aborted || !caps?.agents_enabled) return;
        setAgentCapabilities(caps);
        Promise.allSettled([
          listAgentTemplates(agentClient, { signal }),
          listAgentRuns(agentClient, 10, { signal }),
          getAgentQuota(agentClient, { signal }),
        ]).then(([tplRes, runsRes, quotaRes]) => {
          if (signal.aborted) return;
          if (tplRes.status === "fulfilled") {
            setAgentTemplates(tplRes.value.templates);
          }
          if (runsRes.status === "fulfilled") {
            setAgentRuns(runsRes.value.items);
          }
          if (quotaRes.status === "fulfilled") {
            setAgentQuota(quotaRes.value);
          }
        });
      })
      .catch(() => {
        // Optional AgentOrchestratorServices offline or disabled: keep Mode 1 intact.
      });

    return () => {
      controller.abort();
    };
  }, [agentClient]);

  async function startRun({
    goal,
    selectedDocumentIds,
    onSuccess,
  }: {
    goal: string;
    selectedDocumentIds: string[];
    onSuccess?: () => void;
  }) {
    const trimmed = goal.trim();
    if (!trimmed || agentBusy) return;
    setAgentBusy(true);
    setAgentError(null);
    try {
      const run = await startAgentRun(agentClient, {
        mode: executionMode === "code_mode" ? "code_mode" : "agent",
        goal: trimmed,
        document_ids: selectedDocumentIds,
        template_id: selectedTemplateId,
        enable_code_mode: executionMode === "code_mode",
      });
      setActiveAgentRun(run);
      setAgentRuns((prev) => [
        run,
        ...prev.filter((item) => item.run_id !== run.run_id),
      ]);
      getAgentQuota(agentClient)
        .then(setAgentQuota)
        .catch(() => {});
      onSuccess?.();
    } catch (err) {
      setAgentError(
        err instanceof Error
          ? err.message
          : "No se pudo iniciar la ejecución del agente.",
      );
    } finally {
      setAgentBusy(false);
    }
  }

  async function handleAgentCancel(runId: string) {
    if (!agentClient) return;
    setAgentBusy(true);
    setAgentError(null);
    try {
      const updated = await cancelAgentRun(agentClient, runId);
      setActiveAgentRun(updated);
    } catch (err) {
      setAgentError(
        err instanceof Error
          ? err.message
          : "No se pudo cancelar la ejecución.",
      );
    } finally {
      setAgentBusy(false);
    }
  }

  async function handleAgentDecision(
    runId: string,
    approvalId: string,
    decision: "approve" | "reject",
    comment: string,
  ) {
    if (!agentClient) return;
    setAgentBusy(true);
    setAgentError(null);
    try {
      const updated = await resumeAgentApproval(agentClient, runId, {
        approval_id: approvalId,
        decision,
        comment,
      });
      setActiveAgentRun(updated);
    } catch (err) {
      setAgentError(
        err instanceof Error
          ? err.message
          : "No se pudo registrar la decisión de aprobación.",
      );
    } finally {
      setAgentBusy(false);
    }
  }

  async function handleAgentExport(runId: string, format: "markdown" | "csv") {
    if (!agentClient) return;
    try {
      const content = await exportAgentRunContent(agentClient, runId, format);
      const blob = new Blob([content], {
        type:
          format === "csv"
            ? "text/csv;charset=utf-8"
            : "text/markdown;charset=utf-8",
      });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${runId}.${format === "csv" ? "csv" : "md"}`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setAgentError(
        err instanceof Error
          ? err.message
          : "No se pudo exportar el resultado del agente.",
      );
    }
  }

  async function handleAgentAnalyze(runId: string) {
    if (!agentClient) return;
    setAgentBusy(true);
    setAgentError(null);
    try {
      const result = await analyzeAgentRun(agentClient, runId);
      setAgentAnalysis(result);
    } catch (err) {
      setAgentError(
        err instanceof Error
          ? err.message
          : "No se pudo analizar fechas y montos.",
      );
    } finally {
      setAgentBusy(false);
    }
  }

  async function handleAgentExportPdf(runId: string) {
    if (!agentClient) return;
    setAgentBusy(true);
    setAgentError(null);
    try {
      const result = await exportAgentRunPdf(agentClient, runId);
      if (result.download_url) {
        window.open(result.download_url, "_blank", "noopener,noreferrer");
      } else if (result.fallback_markdown) {
        await handleAgentExport(runId, "markdown");
      }
    } catch (err) {
      setAgentError(
        err instanceof Error
          ? err.message
          : "No se pudo generar el PDF del informe.",
      );
    } finally {
      setAgentBusy(false);
    }
  }

  async function handleAgentRetry(runId: string) {
    if (!agentClient) return;
    setAgentBusy(true);
    setAgentError(null);
    try {
      const retried = await retryAgentRun(agentClient, runId);
      setActiveAgentRun(retried);
      setAgentAnalysis(null);
      setAgentRuns((prev) => [
        retried,
        ...prev.filter((item) => item.run_id !== retried.run_id),
      ]);
      listAgentRunAudit(agentClient, retried.run_id)
        .then((res) => setAgentAuditEvents(res.events))
        .catch(() => {});
    } catch (err) {
      setAgentError(
        err instanceof Error
          ? err.message
          : "No se pudo reintentar la ejecución.",
      );
    } finally {
      setAgentBusy(false);
    }
  }

  function selectRun(run: AgentRun) {
    setActiveAgentRun(run);
    setAgentError(null);
  }

  function dismissRun() {
    setActiveAgentRun(null);
    setAgentAnalysis(null);
    setAgentAuditEvents([]);
    setAgentError(null);
  }

  return {
    agentCapabilities,
    agentTemplates,
    selectedTemplateId,
    setSelectedTemplateId,
    agentRuns,
    agentQuota,
    executionMode,
    setExecutionMode,
    activeAgentRun,
    agentAnalysis,
    agentAuditEvents,
    agentBusy,
    agentError,
    startRun,
    handleAgentCancel,
    handleAgentDecision,
    handleAgentExport,
    handleAgentAnalyze,
    handleAgentExportPdf,
    handleAgentRetry,
    selectRun,
    dismissRun,
  };
}
