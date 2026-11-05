\getenv runtime_password ACCESS_DB_PASSWORD

BEGIN;
SELECT pg_advisory_xact_lock(hashtextextended('blandskron.database.role_provisioning', 0));

SELECT 'CREATE ROLE document_access_runtime'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'document_access_runtime') \gexec
SELECT 'CREATE ROLE document_access_authorizer'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'document_access_authorizer') \gexec

ALTER ROLE document_access_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS
    PASSWORD :'runtime_password';
ALTER ROLE document_access_authorizer NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
GRANT USAGE ON SCHEMA public TO document_access_runtime, document_access_authorizer;
REVOKE CREATE ON SCHEMA public FROM document_access_runtime, document_access_authorizer;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_auth_members WHERE member IN ('document_access_runtime'::regrole, 'document_access_authorizer'::regrole))
       OR has_schema_privilege('document_access_runtime', 'public', 'CREATE')
       OR has_schema_privilege('document_access_authorizer', 'public', 'CREATE') THEN
        RAISE EXCEPTION 'Access roles must not have memberships or CREATE on public';
    END IF;
END
$$;

-- Only the non-login function owner may acquire row locks on authority tables.
GRANT SELECT (id, is_active, is_superuser), UPDATE (id) ON public.auth_user TO document_access_authorizer;
GRANT SELECT (tenant_id, status), UPDATE (tenant_id) ON public.tenants TO document_access_authorizer;
GRANT SELECT (membership_id, tenant_id, user_id, status, role), UPDATE (membership_id)
    ON public.tenant_memberships TO document_access_authorizer;

CREATE OR REPLACE FUNCTION public.access_active_user(identifier bigint)
RETURNS TABLE(id bigint, is_active boolean, is_superuser boolean)
LANGUAGE sql VOLATILE STRICT SECURITY DEFINER SET search_path = pg_catalog, pg_temp
AS $$
    SELECT u.id::bigint, u.is_active, u.is_superuser FROM public.auth_user AS u
    WHERE u.id = identifier AND u.is_active FOR SHARE OF u
$$;
CREATE OR REPLACE FUNCTION public.access_active_tenant(identifier text)
RETURNS TABLE(tenant_id text, status text)
LANGUAGE sql VOLATILE STRICT SECURITY DEFINER SET search_path = pg_catalog, pg_temp
AS $$
    SELECT t.tenant_id, t.status FROM public.tenants AS t
    WHERE t.tenant_id = identifier AND t.status = 'ACTIVE' FOR SHARE OF t
$$;
CREATE OR REPLACE FUNCTION public.access_active_membership(tenant_identifier text, user_identifier text)
RETURNS TABLE(membership_id text, tenant_id text, user_id text, status text, role text)
LANGUAGE sql VOLATILE STRICT SECURITY DEFINER SET search_path = pg_catalog, pg_temp
AS $$
    SELECT m.membership_id, m.tenant_id, m.user_id, m.status, m.role FROM public.tenant_memberships AS m
    WHERE m.tenant_id = tenant_identifier AND m.user_id = user_identifier AND m.status = 'ACTIVE' FOR SHARE OF m
$$;

ALTER FUNCTION public.access_active_user(bigint) OWNER TO document_access_authorizer;
ALTER FUNCTION public.access_active_tenant(text) OWNER TO document_access_authorizer;
ALTER FUNCTION public.access_active_membership(text, text) OWNER TO document_access_authorizer;
REVOKE ALL ON FUNCTION public.access_active_user(bigint), public.access_active_tenant(text),
    public.access_active_membership(text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.access_active_user(bigint), public.access_active_tenant(text),
    public.access_active_membership(text, text) TO document_access_runtime;

GRANT SELECT, DELETE ON public.documents TO document_access_runtime;
-- PostgreSQL requires UPDATE on at least one column for SELECT FOR UPDATE.
GRANT UPDATE (document_id) ON public.documents TO document_access_runtime;
GRANT SELECT (document_id, chunk_index, chunk_content) ON public.document_embeddings TO document_access_runtime;
GRANT SELECT, INSERT ON public.document_assignments, public.document_assignment_events,
    public.notifications, public.document_deletions TO document_access_runtime;
GRANT UPDATE (assigned_by_user_id, assigned_by_role, status, allow_download, rejection_reason,
    signature_value, signed_at, due_at, metadata, updated_at) ON public.document_assignments TO document_access_runtime;
GRANT UPDATE (status, read_at, updated_at) ON public.notifications TO document_access_runtime;
GRANT UPDATE (completed_at, file_deleted, attempts, next_attempt_at, last_error)
    ON public.document_deletions TO document_access_runtime;
GRANT INSERT, SELECT (audit_id, created_at) ON public.audit_logs TO document_access_runtime;

COMMIT;

-- Refuse startup if an existing role has accumulated unrelated privileges.
\ir verify_role.sql
