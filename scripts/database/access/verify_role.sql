BEGIN;
SET LOCAL ROLE document_access_runtime;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = current_user
        AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls))
       OR EXISTS (SELECT 1 FROM pg_auth_members WHERE member = current_user::regrole)
       OR has_schema_privilege(current_user, 'public', 'CREATE')
       OR has_any_column_privilege(current_user, 'public.auth_user', 'SELECT, INSERT, UPDATE')
       OR has_any_column_privilege(current_user, 'public.tenants', 'SELECT, INSERT, UPDATE')
       OR has_any_column_privilege(current_user, 'public.tenant_memberships', 'SELECT, INSERT, UPDATE')
       OR has_column_privilege(current_user, 'public.document_embeddings', 'embedding', 'SELECT')
       OR has_any_column_privilege(current_user, 'public.document_embeddings', 'INSERT, UPDATE')
       OR has_column_privilege(current_user, 'public.documents', 'metadata', 'UPDATE')
       OR has_column_privilege(current_user, 'public.document_assignments', 'tenant_id', 'UPDATE')
       OR has_column_privilege(current_user, 'public.audit_logs', 'action', 'SELECT, UPDATE')
       OR EXISTS (
           SELECT 1 FROM pg_class WHERE relnamespace = 'public'::regnamespace AND relkind IN ('r', 'p', 'v', 'm', 'f')
           AND (
               has_table_privilege(current_user, oid, 'TRUNCATE, TRIGGER')
               OR (relname <> 'documents' AND has_table_privilege(current_user, oid, 'DELETE'))
               OR (relname NOT IN ('documents', 'document_embeddings', 'document_assignments',
                   'document_assignment_events', 'notifications', 'document_deletions', 'audit_logs')
                   AND has_any_column_privilege(current_user, oid, 'SELECT, INSERT, UPDATE, REFERENCES'))
           )
       ) THEN
        RAISE EXCEPTION 'document_access_runtime exceeds its permissions';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_proc AS p JOIN pg_roles AS r ON r.oid = p.proowner
        WHERE p.oid IN ('public.access_active_user(bigint)'::regprocedure,
            'public.access_active_tenant(text)'::regprocedure, 'public.access_active_membership(text,text)'::regprocedure)
        AND (NOT p.prosecdef OR r.rolname <> 'document_access_authorizer' OR r.rolcanlogin
            OR r.rolsuper OR r.rolcreaterole OR r.rolbypassrls
            OR p.proconfig IS DISTINCT FROM ARRAY['search_path=pg_catalog, pg_temp']
            OR EXISTS (SELECT 1 FROM aclexplode(p.proacl) AS a WHERE a.grantee = 0 AND a.privilege_type = 'EXECUTE'))
    ) THEN
        RAISE EXCEPTION 'Access authority functions are not confined';
    END IF;
END
$$;

SELECT * FROM public.documents LIMIT 0;
SELECT document_id, chunk_index, chunk_content FROM public.document_embeddings LIMIT 0;
SELECT * FROM public.document_assignments LIMIT 0;
SELECT * FROM public.document_assignment_events LIMIT 0;
SELECT * FROM public.notifications LIMIT 0;
SELECT * FROM public.document_deletions LIMIT 0;
SELECT * FROM public.access_active_user(NULL::bigint);
SELECT * FROM public.access_active_tenant(NULL::text);
SELECT * FROM public.access_active_membership(NULL::text, NULL::text);

ROLLBACK;
