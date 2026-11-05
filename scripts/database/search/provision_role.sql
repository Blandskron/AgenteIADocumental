\getenv runtime_password SEARCH_DB_PASSWORD

BEGIN;
SELECT pg_advisory_xact_lock(hashtextextended('blandskron.database.role_provisioning', 0));

SELECT 'CREATE ROLE document_search_runtime'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'document_search_runtime') \gexec

ALTER ROLE document_search_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS
    PASSWORD :'runtime_password';
GRANT USAGE ON SCHEMA public TO document_search_runtime;
REVOKE CREATE ON SCHEMA public FROM document_search_runtime;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_auth_members WHERE member = 'document_search_runtime'::regrole)
       OR has_schema_privilege('document_search_runtime', 'public', 'CREATE') THEN
        RAISE EXCEPTION 'document_search_runtime must not have role memberships or CREATE on public';
    END IF;
END
$$;

GRANT SELECT (document_id, tenant_id, owner_user_id, filename, mime_type, status, metadata, processed_at, created_at, updated_at)
    ON public.documents TO document_search_runtime;
GRANT SELECT (chunk_id, document_id, chunk_index, chunk_content, created_at)
    ON public.document_embeddings TO document_search_runtime;
GRANT SELECT (document_id, assigned_to_user_id, assigned_by_user_id, status)
    ON public.document_assignments TO document_search_runtime;

COMMIT;
