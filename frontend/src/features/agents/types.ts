export type ChatExecutionMode = "chat" | "agent" | "code_mode";

export interface AgentCapabilities {
  status: string;
  agents_enabled: boolean;
  code_mode_enabled: boolean;
}

export interface AgentStep {
  index: number;
  tool: string;
  status: string;
  duration_ms: number;
}

export interface AgentPendingApproval {
  approval_id: string;
  action: string;
  summary: string;
}

export interface AgentSource {
  source_index?: number;
  document_id: string;
  chunk_index: number;
  filename?: string;
  quote: string;
}

export interface AgentCodeExecution {
  code: string;
  output: unknown;
  stdout: string;
  duration_ms: number;
  evidence_count: number;
}

export interface AgentRun {
  run_id: string;
  thread_id: string;
  tenant_id: string;
  goal?: string;
  status:
    | "PENDING"
    | "RUNNING"
    | "WAITING_APPROVAL"
    | "SUCCEEDED"
    | "FAILED"
    | "CANCELLED";
  current_step: string;
  steps: AgentStep[];
  pending_approval: AgentPendingApproval | null;
  sources: AgentSource[];
  code_executions?: AgentCodeExecution[];
  result_markdown: string | null;
  provider: string | null;
  steps_used: number;
  usage_tokens: number;
  studio_handoff?: Record<string, unknown> | null;
}

export interface AgentTemplate {
  template_id: string;
  title: string;
  description: string;
  recommended_mode: "agent" | "code_mode";
  default_save_to_studio: boolean;
}

export interface AgentQuotaSnapshot {
  tenant_id: string;
  runs_used: number;
  runs_limit: number;
  tokens_used: number;
  tokens_limit: number;
}

export interface AgentStreamEvent {
  event: "step" | "approval" | "status" | "message";
  data: unknown;
}

export interface StartAgentRunInput {
  mode: "agent" | "code_mode";
  goal: string;
  document_ids: string[];
  template_id?: string;
  enable_code_mode?: boolean;
  save_to_studio?: boolean;
  max_steps?: number;
  max_tokens?: number;
  idempotency_key?: string;
}

export interface ResumeApprovalInput {
  approval_id: string;
  decision: "approve" | "reject";
  comment?: string;
}
