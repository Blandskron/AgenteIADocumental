\getenv runtime_password STUDIO_DB_PASSWORD

BEGIN;

SELECT pg_advisory_xact_lock(hashtextextended('blandskron.database.role_provisioning', 0));

SELECT 'CREATE ROLE studio_runtime'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'studio_runtime') \gexec

ALTER ROLE studio_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS
    PASSWORD :'runtime_password';

GRANT USAGE ON SCHEMA public TO studio_runtime;
GRANT USAGE ON SCHEMA studio TO studio_runtime;
REVOKE CREATE ON SCHEMA public FROM studio_runtime;
REVOKE CREATE ON SCHEMA studio FROM studio_runtime;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_auth_members WHERE member = 'studio_runtime'::regrole)
       OR has_schema_privilege('studio_runtime', 'public', 'CREATE')
       OR has_schema_privilege('studio_runtime', 'studio', 'CREATE') THEN
        RAISE EXCEPTION 'studio_runtime must not have role memberships or CREATE privileges';
    END IF;
END
$$;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
    studio.collections,
    studio.collection_documents,
    studio.studio_jobs,
    studio.artifacts,
    studio.artifact_versions,
    studio.artifact_sources
TO studio_runtime;

GRANT SELECT (document_id, tenant_id, owner_user_id, filename, mime_type, status, metadata, updated_at)
    ON public.documents TO studio_runtime;
GRANT SELECT (chunk_id, document_id, chunk_index, chunk_content, content_tsv, metadata)
    ON public.document_embeddings TO studio_runtime;
GRANT SELECT (document_id, tenant_id, assigned_to_user_id, assigned_by_user_id, status)
    ON public.document_assignments TO studio_runtime;
GRANT SELECT (integration_id, tenant_id, provider, status, config, secrets_encrypted, updated_at)
    ON public.tenant_integrations TO studio_runtime;
GRANT INSERT ON TABLE public.audit_logs TO studio_runtime;

COMMIT;

