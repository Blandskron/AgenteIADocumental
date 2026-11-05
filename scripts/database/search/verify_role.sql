BEGIN;
SET LOCAL ROLE document_search_runtime;

DO $$
BEGIN
    IF has_schema_privilege(current_user, 'public', 'CREATE')
       OR has_column_privilege(current_user, 'public.documents', 'storage_path', 'SELECT')
       OR has_column_privilege(current_user, 'public.documents', 'processing_error', 'SELECT')
       OR has_column_privilege(current_user, 'public.document_embeddings', 'embedding', 'SELECT')
       OR EXISTS (
           SELECT 1 FROM pg_class
           WHERE relnamespace = 'public'::regnamespace AND relkind IN ('r', 'p', 'v', 'm', 'f')
             AND (
                 has_any_column_privilege(current_user, oid, 'INSERT, UPDATE, REFERENCES')
                 OR has_table_privilege(current_user, oid, 'DELETE, TRUNCATE, TRIGGER')
                 OR (
                     relname NOT IN ('documents', 'document_embeddings', 'document_assignments')
                     AND has_any_column_privilege(current_user, oid, 'SELECT')
                 )
             )
       ) THEN
        RAISE EXCEPTION 'document_search_runtime exceeds its permissions';
    END IF;
END
$$;

SELECT document_id, tenant_id, owner_user_id, filename, mime_type, status, metadata, processed_at, created_at, updated_at
FROM public.documents LIMIT 0;
SELECT chunk_id, document_id, chunk_index, chunk_content, created_at
FROM public.document_embeddings LIMIT 0;
SELECT document_id, assigned_to_user_id, assigned_by_user_id, status
FROM public.document_assignments LIMIT 0;

ROLLBACK;
