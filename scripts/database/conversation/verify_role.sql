BEGIN;

SET LOCAL ROLE conversation_runtime;

DO $$
BEGIN
    IF current_user <> 'conversation_runtime'
       OR has_schema_privilege(current_user, 'public', 'CREATE')
       OR has_table_privilege(current_user, 'public.auth_user', 'SELECT')
       OR has_table_privilege(current_user, 'public.documents', 'SELECT')
       OR has_any_column_privilege(current_user, 'public.documents', 'UPDATE')
       OR has_any_column_privilege(current_user, 'public.document_assignments', 'UPDATE')
       OR has_column_privilege(current_user, 'public.documents', 'storage_path', 'SELECT')
       OR has_column_privilege(current_user, 'public.conversations', 'owner_user_id', 'UPDATE')
       OR has_table_privilege(current_user, 'public.conversation_messages', 'DELETE') THEN
        RAISE EXCEPTION 'conversation_runtime exceeds its permissions';
    END IF;
END
$$;

SELECT document_id, owner_user_id, tenant_id, metadata FROM public.documents LIMIT 0;
SELECT document_id, assigned_to_user_id, assigned_by_user_id, status FROM public.document_assignments LIMIT 0;

ROLLBACK;
