\getenv runtime_password RAG_CHAT_DB_PASSWORD

BEGIN;

SELECT pg_advisory_xact_lock(hashtextextended('blandskron.database.role_provisioning', 0));

SELECT 'CREATE ROLE rag_chat_runtime'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rag_chat_runtime') \gexec

ALTER ROLE rag_chat_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS
    PASSWORD :'runtime_password';

GRANT USAGE ON SCHEMA public TO rag_chat_runtime;
REVOKE CREATE ON SCHEMA public FROM rag_chat_runtime;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_auth_members WHERE member = 'rag_chat_runtime'::regrole)
       OR has_schema_privilege('rag_chat_runtime', 'public', 'CREATE') THEN
        RAISE EXCEPTION 'rag_chat_runtime must not have role memberships or CREATE on public';
    END IF;
END
$$;

GRANT SELECT (message_id, session_id, owner_user_id, role, content, created_at),
    INSERT (session_id, owner_user_id, role, content, sources)
    ON public.chat_messages TO rag_chat_runtime;
GRANT SELECT (document_id, owner_user_id, tenant_id, metadata)
    ON public.documents TO rag_chat_runtime;
GRANT SELECT (chunk_id, document_id, chunk_index, chunk_content, embedding, metadata)
    ON public.document_embeddings TO rag_chat_runtime;
GRANT SELECT (document_id, assigned_to_user_id, assigned_by_user_id, status)
    ON public.document_assignments TO rag_chat_runtime;

COMMIT;
