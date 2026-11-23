-- Isolated schema for AgentOrchestratorServices (AG-003).
-- Keeps agent state, runs, human approvals and daily quotas completely separate from public.documents.

CREATE SCHEMA IF NOT EXISTS agents;

CREATE TABLE IF NOT EXISTS agents.agent_runs (
    run_id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL REFERENCES public.tenants(tenant_id) ON DELETE CASCADE,
    owner_user_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'agent' CHECK (mode IN ('agent', 'code_mode')),
    goal TEXT NOT NULL,
    document_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (
        status IN ('PENDING', 'RUNNING', 'WAITING_APPROVAL', 'SUCCEEDED', 'FAILED', 'CANCELLED')
    ),
    current_step TEXT NOT NULL DEFAULT 'queued',
    steps JSONB NOT NULL DEFAULT '[]'::jsonb,
    sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    code_executions JSONB NOT NULL DEFAULT '[]'::jsonb,
    pending_approval JSONB,
    studio_handoff JSONB,
    result_markdown TEXT,
    error_code TEXT,
    error_message TEXT,
    provider TEXT,
    steps_used INTEGER NOT NULL DEFAULT 0,
    usage_tokens INTEGER NOT NULL DEFAULT 0,
    cancel_requested BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT agent_runs_tenant_idempotency_unique UNIQUE (tenant_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS agents.agent_approvals (
    approval_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES agents.agent_runs(run_id) ON DELETE CASCADE,
    tenant_id TEXT NOT NULL REFERENCES public.tenants(tenant_id) ON DELETE CASCADE,
    requested_by_user_id TEXT NOT NULL,
    action TEXT NOT NULL,
    summary TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    decision TEXT NOT NULL DEFAULT 'PENDING' CHECK (decision IN ('PENDING', 'APPROVED', 'REJECTED')),
    decided_by_user_id TEXT,
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decided_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS agents.agent_usage_daily (
    tenant_id TEXT NOT NULL REFERENCES public.tenants(tenant_id) ON DELETE CASCADE,
    usage_date DATE NOT NULL,
    runs_count INTEGER NOT NULL DEFAULT 0,
    tokens_used INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, usage_date)
);

CREATE TABLE IF NOT EXISTS agents.agent_checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_seq INTEGER NOT NULL,
    tenant_id TEXT NOT NULL REFERENCES public.tenants(tenant_id) ON DELETE CASCADE,
    owner_user_id TEXT NOT NULL,
    node_name TEXT NOT NULL,
    state_format TEXT NOT NULL DEFAULT 'strict_json',
    state_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (thread_id, checkpoint_seq)
);

CREATE INDEX IF NOT EXISTS agent_runs_tenant_owner_idx
    ON agents.agent_runs (tenant_id, owner_user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS agent_approvals_run_idx
    ON agents.agent_approvals (run_id, decision);

CREATE INDEX IF NOT EXISTS agent_checkpoints_tenant_owner_idx
    ON agents.agent_checkpoints (tenant_id, owner_user_id, thread_id, checkpoint_seq DESC);

-- Additive migration for existing installations (EVO-004)
ALTER TABLE agents.agent_runs
    ADD COLUMN IF NOT EXISTS code_executions JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS pending_approval JSONB,
    ADD COLUMN IF NOT EXISTS studio_handoff JSONB;

