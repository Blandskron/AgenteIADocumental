import type { MaybeClient } from "@/shared/api/types.ts";
import { requireClient } from "@/shared/api/types.ts";
import type {
  AgentAuditEvent,
  AgentCapabilities,
  AgentPdfExportResult,
  AgentQuotaSnapshot,
  AgentRun,
  AgentRunAnalysis,
  AgentTemplate,
  ResumeApprovalInput,
  StartAgentRunInput,
} from "../types.ts";

export function getAgentHealth(agentClient: MaybeClient) {
  return requireClient(agentClient)<AgentCapabilities>("/api/v1/health", {
    method: "GET",
  });
}

export function startAgentRun(
  agentClient: MaybeClient,
  input: StartAgentRunInput,
) {
  return requireClient(agentClient)<AgentRun>("/api/v1/agents/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function listAgentRuns(agentClient: MaybeClient, limit = 20) {
  return requireClient(agentClient)<{ items: AgentRun[] }>(
    `/api/v1/agents/runs?limit=${encodeURIComponent(String(limit))}`,
    { method: "GET" },
  );
}

export function getAgentRun(agentClient: MaybeClient, runId: string) {
  return requireClient(agentClient)<AgentRun>(
    `/api/v1/agents/runs/${encodeURIComponent(runId)}`,
    { method: "GET" },
  );
}

export function resumeAgentApproval(
  agentClient: MaybeClient,
  runId: string,
  payload: ResumeApprovalInput,
) {
  return requireClient(agentClient)<AgentRun>(
    `/api/v1/agents/runs/${encodeURIComponent(runId)}/resume`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}

export function cancelAgentRun(agentClient: MaybeClient, runId: string) {
  return requireClient(agentClient)<AgentRun>(
    `/api/v1/agents/runs/${encodeURIComponent(runId)}/cancel`,
    { method: "POST" },
  );
}

export function listAgentTemplates(agentClient: MaybeClient) {
  return requireClient(agentClient)<{
    tenant_id: string;
    templates: AgentTemplate[];
  }>("/api/v1/agents/templates", { method: "GET" });
}

export function getAgentQuota(agentClient: MaybeClient) {
  return requireClient(agentClient)<AgentQuotaSnapshot>(
    "/api/v1/agents/quota",
    {
      method: "GET",
    },
  );
}

export function exportAgentRunContent(
  agentClient: MaybeClient,
  runId: string,
  format: "markdown" | "csv",
) {
  return requireClient(agentClient)<string>(
    `/api/v1/agents/runs/${encodeURIComponent(runId)}/export?format=${encodeURIComponent(format)}`,
    { method: "GET" },
  );
}

export function analyzeAgentRun(agentClient: MaybeClient, runId: string) {
  return requireClient(agentClient)<AgentRunAnalysis>(
    `/api/v1/agents/runs/${encodeURIComponent(runId)}/analyze`,
    { method: "POST" },
  );
}

export function exportAgentRunPdf(agentClient: MaybeClient, runId: string) {
  return requireClient(agentClient)<AgentPdfExportResult>(
    `/api/v1/agents/runs/${encodeURIComponent(runId)}/export-pdf`,
    { method: "POST" },
  );
}

export function retryAgentRun(agentClient: MaybeClient, runId: string) {
  return requireClient(agentClient)<AgentRun>(
    `/api/v1/agents/runs/${encodeURIComponent(runId)}/retry`,
    { method: "POST" },
  );
}

export function listAgentRunAudit(agentClient: MaybeClient, runId: string) {
  return requireClient(agentClient)<{
    run_id: string;
    events: AgentAuditEvent[];
  }>(`/api/v1/agents/runs/${encodeURIComponent(runId)}/audit`, {
    method: "GET",
  });
}
