-- Safe inside provisioning's transaction; read-only assertions, no SET ROLE or COMMIT.
DO $$
DECLARE
    role_name text;
    role_id oid;
    col record;
    allowed boolean;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['document_transfer_runtime', 'document_transfer_reference_owner'] LOOP
        SELECT oid INTO STRICT role_id FROM pg_roles WHERE rolname=role_name
            AND NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolreplication AND NOT rolbypassrls
            AND NOT rolinherit AND rolcanlogin=(role_name='document_transfer_runtime');
        IF EXISTS (SELECT 1 FROM pg_auth_members WHERE member=role_id)
           OR has_schema_privilege(role_id, 'public', 'CREATE') THEN
            RAISE EXCEPTION 'Transfer roles must not inherit memberships or CREATE on public';
        END IF;
        FOR col IN SELECT c.oid, c.relname, a.attnum, a.attname FROM pg_class c JOIN pg_attribute a ON a.attrelid=c.oid
            WHERE c.relnamespace='public'::regnamespace AND c.relkind IN ('r','p','v','m','f') AND a.attnum>0 AND NOT a.attisdropped LOOP
            allowed := CASE WHEN role_name='document_transfer_reference_owner' THEN col.relname='documents' AND col.attname='document_id'
                ELSE col.relname='transfer_events'
                  OR (col.relname='documents' AND col.attname IN ('document_id','tenant_id','owner_user_id','metadata'))
                  OR (col.relname='document_assignments' AND col.attname IN ('assignment_id','document_id','assigned_to_user_id','assigned_by_user_id','status')) END;
            IF has_column_privilege(role_id,col.oid,col.attnum,'SELECT') IS DISTINCT FROM allowed THEN
                RAISE EXCEPTION 'Transfer role exceeds allowed read columns';
            END IF;
            allowed := role_name='document_transfer_runtime' AND col.relname='transfer_events' AND col.attname IN ('owner_user_id','document_id','filename','direction','status','progress','size_bytes','metadata');
            IF has_column_privilege(role_id,col.oid,col.attnum,'INSERT') IS DISTINCT FROM allowed THEN
                RAISE EXCEPTION 'Transfer role exceeds allowed insert columns';
            END IF;
            allowed := CASE WHEN role_name='document_transfer_reference_owner' THEN col.relname='documents' AND col.attname='document_id'
                ELSE col.relname='transfer_events' AND col.attname IN ('document_id','status','progress','size_bytes','metadata','updated_at') END;
            IF has_column_privilege(role_id,col.oid,col.attnum,'UPDATE') IS DISTINCT FROM allowed THEN
                RAISE EXCEPTION 'Transfer role exceeds allowed update columns';
            END IF;
            IF has_column_privilege(role_id,col.oid,col.attnum,'REFERENCES')
               OR has_table_privilege(role_id,col.oid,'TRUNCATE,TRIGGER')
               OR (has_table_privilege(role_id,col.oid,'DELETE') AND NOT (
                   role_name='document_transfer_runtime' AND col.relname='transfer_events')) THEN
                RAISE EXCEPTION 'Transfer role exceeds allowed table operations';
            END IF;
        END LOOP;
        IF EXISTS (SELECT 1 FROM pg_class c, LATERAL aclexplode(c.relacl) acl
                   WHERE c.relnamespace='public'::regnamespace AND acl.grantee=role_id AND acl.is_grantable)
           OR EXISTS (SELECT 1 FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid,
                      LATERAL aclexplode(a.attacl) acl WHERE c.relnamespace='public'::regnamespace
                      AND acl.grantee=role_id AND acl.is_grantable) THEN
            RAISE EXCEPTION 'Transfer roles must not delegate table or column privileges';
        END IF;
        IF EXISTS (SELECT 1 FROM pg_class WHERE CASE WHEN relnamespace='public'::regnamespace AND relkind='S'
                   THEN has_sequence_privilege(role_id,oid,'USAGE,SELECT,UPDATE') ELSE false END) THEN
            RAISE EXCEPTION 'Transfer roles must not access application sequences';
        END IF;
    END LOOP;
    IF NOT EXISTS (SELECT 1 FROM pg_proc WHERE oid='public.transfer_lock_document_reference(text)'::regprocedure
        AND proowner='document_transfer_reference_owner'::regrole AND prosecdef AND proisstrict AND provolatile='v'
        AND proconfig @> ARRAY['search_path=pg_catalog, pg_temp'])
       OR NOT has_function_privilege('document_transfer_runtime','public.transfer_lock_document_reference(text)','EXECUTE')
       OR EXISTS (SELECT 1 FROM pg_proc p, LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) acl
           WHERE p.oid='public.transfer_lock_document_reference(text)'::regprocedure AND acl.privilege_type='EXECUTE'
             AND (acl.grantee NOT IN ('document_transfer_reference_owner'::regrole, 'document_transfer_runtime'::regrole)
                  OR (acl.grantee='document_transfer_runtime'::regrole AND acl.is_grantable))) THEN
        RAISE EXCEPTION 'Transfer reference function owner, search path or ACL is invalid';
    END IF;
END
$$;
