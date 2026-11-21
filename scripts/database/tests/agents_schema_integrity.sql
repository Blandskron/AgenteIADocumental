-- Integrity test for isolated agents.* schema (AG-003).
BEGIN;

INSERT INTO public.tenants (tenant_id, name) VALUES ('ag-test-tenant', 'Synthetic Agent Org')
ON CONFLICT (tenant_id) DO NOTHING;

INSERT INTO agents.agent_runs (
    run_id, thread_id, tenant_id, owner_user_id, idempotency_key, mode, goal, status
) VALUES (
    'run-sql-1', 'thr-sql-1', 'ag-test-tenant', '42', 'idem-sql-1', 'agent', 'Prueba de esquema agents', 'PENDING'
);

INSERT INTO agents.agent_approvals (
    approval_id, run_id, tenant_id, requested_by_user_id, action, summary
) VALUES (
    'apr-sql-1', 'run-sql-1', 'ag-test-tenant', '42', 'save_studio_artifact', 'Confirmar guardado'
);

INSERT INTO agents.agent_usage_daily (tenant_id, usage_date, runs_count, tokens_used)
VALUES ('ag-test-tenant', CURRENT_DATE, 1, 500);

DO $$
DECLARE
    cnt INTEGER;
BEGIN
    SELECT COUNT(*) INTO cnt FROM agents.agent_runs WHERE run_id = 'run-sql-1';
    IF cnt <> 1 THEN
        RAISE EXCEPTION 'Expected 1 agent_run row, found %', cnt;
    END IF;
END
$$;

ROLLBACK;

