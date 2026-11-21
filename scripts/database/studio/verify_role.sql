BEGIN;

SET LOCAL ROLE studio_runtime;

DO $$
BEGIN
    IF has_schema_privilege(current_user, 'public', 'CREATE')
       OR has_schema_privilege(current_user, 'studio', 'CREATE')
       OR has_table_privilege(current_user, 'public.auth_user', 'SELECT')
       OR has_column_privilege(current_user, 'public.documents', 'storage_path', 'SELECT')
       OR has_any_column_privilege(current_user, 'public.documents', 'UPDATE')
       OR has_any_column_privilege(current_user, 'public.tenant_integrations', 'UPDATE')
       OR NOT has_table_privilege(current_user, 'studio.studio_jobs', 'INSERT')
       OR NOT has_table_privilege(current_user, 'studio.artifacts', 'SELECT') THEN
        RAISE EXCEPTION 'studio_runtime permissions mismatch';
    END IF;
END
$$;

SELECT collection_id, tenant_id, title FROM studio.collections LIMIT 0;
SELECT job_id, status, step FROM studio.studio_jobs LIMIT 0;
SELECT artifact_id, status FROM studio.artifacts LIMIT 0;
SELECT document_id, tenant_id, filename FROM public.documents LIMIT 0;
SELECT chunk_id, document_id, chunk_index, chunk_content FROM public.document_embeddings LIMIT 0;

ROLLBACK;

