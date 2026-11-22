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

export function getAgentHealth(
  agentClient: MaybeClient,
  { signal }: { signal?: AbortSignal } = {},
) {
  return requireClient(agentClient)<AgentCapabilities>("/api/v1/health", {
    method: "GET",
    ...(signal ? { signal } : {}),
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

export async function listAgentRuns(
  agentClient: MaybeClient,
  limit = 20,
  { signal }: { signal?: AbortSignal } = {},
): Promise<{ items: AgentRun[] }> {
  const raw = await requireClient(agentClient)<{ items: AgentRun[] }>(
    `/api/v1/agents/runs?limit=${encodeURIComponent(String(limit))}`,
    { method: "GET", ...(signal ? { signal } : {}) },
  );
  return {
    items: Array.isArray(raw?.items) ? raw.items : [],
  };
}

export function getAgentRun(
  agentClient: MaybeClient,
  runId: string,
  { signal }: { signal?: AbortSignal } = {},
) {
  return requireClient(agentClient)<AgentRun>(
    `/api/v1/agents/runs/${encodeURIComponent(runId)}`,
    { method: "GET", ...(signal ? { signal } : {}) },
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

export async function listAgentTemplates(
  agentClient: MaybeClient,
  { signal }: { signal?: AbortSignal } = {},
): Promise<{ tenant_id: string; templates: AgentTemplate[] }> {
  const raw = await requireClient(agentClient)<{
    tenant_id: string;
    templates: AgentTemplate[];
  }>("/api/v1/agents/templates", {
    method: "GET",
    ...(signal ? { signal } : {}),
  });
  return {
    tenant_id: raw?.tenant_id ?? "",
    templates: Array.isArray(raw?.templates) ? raw.templates : [],
  };
}

export function getAgentQuota(
  agentClient: MaybeClient,
  { signal }: { signal?: AbortSignal } = {},
) {
  return requireClient(agentClient)<AgentQuotaSnapshot>(
    "/api/v1/agents/quota",
    {
      method: "GET",
      ...(signal ? { signal } : {}),
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

export async function listAgentRunAudit(
  agentClient: MaybeClient,
  runId: string,
  { signal }: { signal?: AbortSignal } = {},
): Promise<{ run_id: string; events: AgentAuditEvent[] }> {
  const raw = await requireClient(agentClient)<{
    run_id: string;
    events: AgentAuditEvent[];
  }>(`/api/v1/agents/runs/${encodeURIComponent(runId)}/audit`, {
    method: "GET",
    ...(signal ? { signal } : {}),
  });
  return {
    run_id: raw?.run_id ?? runId,
    events: Array.isArray(raw?.events) ? raw.events : [],
  };
}
