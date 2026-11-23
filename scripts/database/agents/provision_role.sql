\getenv runtime_password AGENT_DB_PASSWORD

BEGIN;

SELECT pg_advisory_xact_lock(hashtextextended('blandskron.database.role_provisioning', 0));

SELECT 'CREATE ROLE agent_runtime'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_runtime') \gexec

ALTER ROLE agent_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS
    PASSWORD :'runtime_password';

GRANT USAGE ON SCHEMA agents TO agent_runtime;
GRANT USAGE ON SCHEMA public TO agent_runtime;
REVOKE CREATE ON SCHEMA agents FROM agent_runtime;
REVOKE CREATE ON SCHEMA public FROM agent_runtime;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_auth_members WHERE member = 'agent_runtime'::regrole)
       OR has_schema_privilege('agent_runtime', 'public', 'CREATE')
       OR has_schema_privilege('agent_runtime', 'agents', 'CREATE') THEN
        RAISE EXCEPTION 'agent_runtime must not have role memberships or CREATE privileges';
    END IF;
END
$$;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
    agents.agent_runs,
    agents.agent_approvals,
    agents.agent_usage_daily,
    agents.agent_checkpoints,
    agents.agent_findings
TO agent_runtime;

-- Strict isolation: agent_runtime NEVER reads public.documents or public.document_embeddings directly.
-- It only reads tenant_integrations (to resolve active provider) and reads/appends agent events in public.audit_logs.
GRANT SELECT (integration_id, tenant_id, provider, status, config, secrets_encrypted, updated_at)
    ON public.tenant_integrations TO agent_runtime;
GRANT SELECT, INSERT ON TABLE public.audit_logs TO agent_runtime;

COMMIT;

