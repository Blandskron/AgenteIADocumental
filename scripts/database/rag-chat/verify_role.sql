BEGIN;

SET LOCAL ROLE rag_chat_runtime;

DO $$
BEGIN
    IF has_schema_privilege(current_user, 'public', 'CREATE')
       OR has_table_privilege(current_user, 'public.auth_user', 'SELECT')
       OR has_table_privilege(current_user, 'public.conversations', 'SELECT')
       OR has_column_privilege(current_user, 'public.documents', 'storage_path', 'SELECT')
       OR has_any_column_privilege(current_user, 'public.documents', 'UPDATE')
       OR has_any_column_privilege(current_user, 'public.document_embeddings', 'INSERT')
       OR has_any_column_privilege(current_user, 'public.document_assignments', 'UPDATE')
       OR has_any_column_privilege(current_user, 'public.chat_messages', 'UPDATE')
       OR has_table_privilege(current_user, 'public.chat_messages', 'DELETE') THEN
        RAISE EXCEPTION 'rag_chat_runtime exceeds its permissions';
    END IF;
END
$$;

INSERT INTO public.chat_messages (session_id, owner_user_id, role, content, sources)
VALUES ('synthetic-role-probe', '42', 'user', 'Synthetic question', '[]')
RETURNING message_id, created_at;

SELECT document_id, owner_user_id, tenant_id, metadata FROM public.documents LIMIT 0;
SELECT chunk_id, document_id, chunk_index, chunk_content, embedding, metadata
FROM public.document_embeddings LIMIT 0;
SELECT document_id, assigned_to_user_id, assigned_by_user_id, status
FROM public.document_assignments LIMIT 0;

ROLLBACK;
