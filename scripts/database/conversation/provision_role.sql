\getenv runtime_password CONVERSATION_DB_PASSWORD

BEGIN;

-- Role provisioners share the public schema ACL and must update it serially.
SELECT pg_advisory_xact_lock(hashtextextended('blandskron.database.role_provisioning', 0));

SELECT 'CREATE ROLE conversation_runtime'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'conversation_runtime') \gexec

ALTER ROLE conversation_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS
    PASSWORD :'runtime_password';

GRANT USAGE ON SCHEMA public TO conversation_runtime;
REVOKE CREATE ON SCHEMA public FROM conversation_runtime;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_auth_members
        WHERE member = 'conversation_runtime'::regrole
    ) OR has_schema_privilege('conversation_runtime', 'public', 'CREATE') THEN
        RAISE EXCEPTION 'conversation_runtime must not have role memberships or CREATE on public';
    END IF;
END
$$;

GRANT SELECT, INSERT, DELETE ON public.conversations TO conversation_runtime;
GRANT UPDATE (title, archived, updated_at) ON public.conversations TO conversation_runtime;
GRANT SELECT, INSERT ON public.conversation_messages TO conversation_runtime;
GRANT SELECT, INSERT, DELETE ON public.conversation_documents TO conversation_runtime;
GRANT SELECT (document_id, owner_user_id, tenant_id, metadata) ON public.documents TO conversation_runtime;
GRANT SELECT (document_id, assigned_to_user_id, assigned_by_user_id, status)
    ON public.document_assignments TO conversation_runtime;

COMMIT;
