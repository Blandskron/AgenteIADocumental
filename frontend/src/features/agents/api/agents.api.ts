import type { MaybeClient } from "@/shared/api/types.ts";
import { requireClient } from "@/shared/api/types.ts";
import type {
  AgentCapabilities,
  AgentRun,
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
