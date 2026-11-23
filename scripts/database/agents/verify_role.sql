-- Verify agent_runtime least-privilege isolation (AG-003).
DO $$
BEGIN
    IF has_table_privilege('agent_runtime', 'public.documents', 'SELECT') THEN
        RAISE EXCEPTION 'agent_runtime must NOT have SELECT on public.documents';
    END IF;
    IF has_table_privilege('agent_runtime', 'public.document_embeddings', 'SELECT') THEN
        RAISE EXCEPTION 'agent_runtime must NOT have SELECT on public.document_embeddings';
    END IF;
    IF NOT has_table_privilege('agent_runtime', 'agents.agent_runs', 'INSERT') THEN
        RAISE EXCEPTION 'agent_runtime must have INSERT on agents.agent_runs';
    END IF;
    IF NOT has_table_privilege('agent_runtime', 'agents.agent_checkpoints', 'INSERT') THEN
        RAISE EXCEPTION 'agent_runtime must have INSERT on agents.agent_checkpoints';
    END IF;
    IF NOT has_table_privilege('agent_runtime', 'agents.agent_checkpoints', 'SELECT') THEN
        RAISE EXCEPTION 'agent_runtime must have SELECT on agents.agent_checkpoints';
    END IF;
    IF NOT has_table_privilege('agent_runtime', 'public.audit_logs', 'INSERT') THEN
        RAISE EXCEPTION 'agent_runtime must have INSERT on public.audit_logs';
    END IF;
    IF NOT has_table_privilege('agent_runtime', 'public.audit_logs', 'SELECT') THEN
        RAISE EXCEPTION 'agent_runtime must have SELECT on public.audit_logs';
    END IF;
END
$$;

