\getenv runtime_password EMBEDDING_DB_PASSWORD

BEGIN;

SELECT pg_advisory_xact_lock(hashtextextended('blandskron.database.role_provisioning', 0));

SELECT 'CREATE ROLE embedding_runtime'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'embedding_runtime') \gexec

ALTER ROLE embedding_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS
    PASSWORD :'runtime_password';

GRANT USAGE ON SCHEMA public TO embedding_runtime;
REVOKE CREATE ON SCHEMA public FROM embedding_runtime;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_auth_members WHERE member = 'embedding_runtime'::regrole)
       OR has_schema_privilege('embedding_runtime', 'public', 'CREATE') THEN
        RAISE EXCEPTION 'embedding_runtime must not have role memberships or CREATE on public';
    END IF;
END
$$;

GRANT SELECT (document_id, tenant_id, owner_user_id, owner_area_id, created_by_user_id, filename,
              storage_path, mime_type, status, metadata, processing_error, processed_at, created_at, updated_at),
    INSERT (tenant_id, owner_user_id, owner_area_id, created_by_user_id, filename,
            storage_path, mime_type, status, metadata, processing_error, processed_at),
    UPDATE (status, processing_error, processed_at, updated_at)
    ON public.documents TO embedding_runtime;

GRANT SELECT (chunk_id, document_id, created_at),
    INSERT (document_id, chunk_index, chunk_content, embedding, embedding_model, metadata),
    DELETE ON public.document_embeddings TO embedding_runtime;

COMMIT;
