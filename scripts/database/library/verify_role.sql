-- Safe inside provisioning's transaction; read-only assertions, no SET ROLE or COMMIT.
DO $$
DECLARE
    role_name text;
    role_id oid;
    col record;
    allowed boolean;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['document_library_runtime', 'document_library_reference_owner'] LOOP
        SELECT oid INTO STRICT role_id FROM pg_roles WHERE rolname=role_name
            AND NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolreplication AND NOT rolbypassrls
            AND NOT rolinherit AND rolcanlogin=(role_name='document_library_runtime');
        IF EXISTS (SELECT 1 FROM pg_auth_members WHERE member=role_id)
           OR has_schema_privilege(role_id, 'public', 'CREATE') THEN
            RAISE EXCEPTION 'Library roles must not inherit memberships or CREATE on public';
        END IF;
        FOR col IN SELECT c.oid, c.relname, a.attnum, a.attname FROM pg_class c JOIN pg_attribute a ON a.attrelid=c.oid
            WHERE c.relnamespace='public'::regnamespace AND c.relkind IN ('r','p','v','m','f') AND a.attnum>0 AND NOT a.attisdropped LOOP
            allowed := CASE WHEN role_name='document_library_reference_owner' THEN col.relname='documents' AND col.attname='document_id'
                ELSE col.relname IN ('document_folders','document_folder_items','document_favorites')
                  OR (col.relname='documents' AND col.attname IN ('document_id','tenant_id','owner_user_id','owner_area_id','created_by_user_id',
                      'filename','mime_type','status','metadata','created_at','updated_at'))
                  OR (col.relname='document_assignments' AND col.attname IN ('document_id','assigned_to_user_id','assigned_by_user_id','status'))
                  OR (col.relname='document_embeddings' AND col.attname IN ('chunk_id','document_id')) END;
            IF has_column_privilege(role_id,col.oid,col.attnum,'SELECT') IS DISTINCT FROM allowed THEN
                RAISE EXCEPTION 'Library role exceeds allowed read columns';
            END IF;
            allowed := role_name='document_library_runtime' AND col.relname IN ('document_folders','document_folder_items','document_favorites');
            IF has_column_privilege(role_id,col.oid,col.attnum,'INSERT') IS DISTINCT FROM allowed THEN
                RAISE EXCEPTION 'Library role exceeds allowed insert columns';
            END IF;
            allowed := CASE WHEN role_name='document_library_reference_owner' THEN col.relname='documents' AND col.attname='document_id'
                ELSE col.relname='document_folders' AND col.attname IN ('name','metadata','updated_at') END;
            IF has_column_privilege(role_id,col.oid,col.attnum,'UPDATE') IS DISTINCT FROM allowed THEN
                RAISE EXCEPTION 'Library role exceeds allowed update columns';
            END IF;
            IF has_column_privilege(role_id,col.oid,col.attnum,'REFERENCES')
               OR has_table_privilege(role_id,col.oid,'TRUNCATE,TRIGGER')
               OR (has_table_privilege(role_id,col.oid,'DELETE') AND NOT (
                   role_name='document_library_runtime' AND col.relname IN ('document_folders','document_folder_items','document_favorites'))) THEN
                RAISE EXCEPTION 'Library role exceeds allowed table operations';
            END IF;
        END LOOP;
        IF EXISTS (SELECT 1 FROM pg_class WHERE CASE WHEN relnamespace='public'::regnamespace AND relkind='S'
                   THEN has_sequence_privilege(role_id,oid,'USAGE,SELECT,UPDATE') ELSE false END) THEN
            RAISE EXCEPTION 'Library roles must not access application sequences';
        END IF;
    END LOOP;
    IF NOT EXISTS (SELECT 1 FROM pg_proc WHERE oid='public.library_lock_document_reference(text)'::regprocedure
        AND proowner='document_library_reference_owner'::regrole AND prosecdef AND proisstrict AND provolatile='v'
        AND proconfig @> ARRAY['search_path=pg_catalog, pg_temp'])
       OR NOT has_function_privilege('document_library_runtime','public.library_lock_document_reference(text)','EXECUTE')
       OR EXISTS (SELECT 1 FROM pg_proc p, LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) acl
           WHERE p.oid='public.library_lock_document_reference(text)'::regprocedure AND acl.grantee=0 AND acl.privilege_type='EXECUTE') THEN
        RAISE EXCEPTION 'Library reference function owner, search path or ACL is invalid';
    END IF;
END
$$;
