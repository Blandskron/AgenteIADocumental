DO $$
DECLARE role_name text; role_id oid; col record; allowed boolean; fn record;
BEGIN
  FOREACH role_name IN ARRAY ARRAY['export_runtime','export_helper_owner'] LOOP
    SELECT oid INTO STRICT role_id FROM pg_roles WHERE rolname=role_name AND NOT rolsuper AND NOT rolcreatedb
      AND NOT rolcreaterole AND NOT rolreplication AND NOT rolbypassrls AND NOT rolinherit AND rolcanlogin=(role_name='export_runtime');
    IF EXISTS(SELECT 1 FROM pg_auth_members WHERE member=role_id) OR has_schema_privilege(role_id,'public','CREATE') THEN
      RAISE EXCEPTION 'Export role has memberships or schema CREATE';
    END IF;
    FOR col IN SELECT c.oid,c.relname,a.attnum,a.attname FROM pg_class c JOIN pg_attribute a ON a.attrelid=c.oid
      WHERE c.relnamespace='public'::regnamespace AND c.relkind IN ('r','p','v','m','f') AND a.attnum>0 AND NOT a.attisdropped LOOP
      allowed := CASE WHEN role_name='export_runtime' THEN col.relname='document_exports' AND col.attname NOT IN ('storage_path','error_message') ELSE
        (col.relname='auth_user' AND col.attname IN ('id','is_active','password')) OR
        (col.relname='conversations' AND col.attname IN ('conversation_id','owner_user_id')) OR
        (col.relname='conversation_messages' AND col.attname IN ('message_id','conversation_id','owner_user_id')) OR
        (col.relname='document_exports' AND col.attname IN ('export_id','owner_user_id')) END;
      IF has_column_privilege(role_id,col.oid,col.attnum,'SELECT') IS DISTINCT FROM allowed THEN RAISE EXCEPTION 'Export SELECT exceeds allowed columns'; END IF;
      allowed := role_name='export_runtime' AND col.relname='document_exports' AND col.attname IN
        ('owner_user_id','source_type','source_id','conversation_id','message_id','title','format','status','filename','storage_path',
         'mime_type','file_size_bytes','metadata','error_message','pdf_data','pdf_sha256','expires_at','operation_key','request_sha256');
      IF has_column_privilege(role_id,col.oid,col.attnum,'INSERT') IS DISTINCT FROM allowed THEN RAISE EXCEPTION 'Export INSERT exceeds allowed columns'; END IF;
      allowed := role_name='export_helper_owner' AND
        ((col.relname='auth_user' AND col.attname='id') OR (col.relname='conversations' AND col.attname='conversation_id') OR
         (col.relname='conversation_messages' AND col.attname='message_id') OR (col.relname='document_exports' AND col.attname='export_id'));
      IF has_column_privilege(role_id,col.oid,col.attnum,'UPDATE') IS DISTINCT FROM allowed THEN RAISE EXCEPTION 'Export UPDATE exceeds row-lock columns'; END IF;
      IF has_table_privilege(role_id,col.oid,'DELETE') IS DISTINCT FROM (role_name='export_runtime' AND col.relname='document_exports')
        OR has_table_privilege(role_id,col.oid,'TRUNCATE,TRIGGER') OR has_column_privilege(role_id,col.oid,col.attnum,'REFERENCES') THEN
        RAISE EXCEPTION 'Export table privilege exceeds allowed operations';
      END IF;
    END LOOP;
    IF EXISTS(SELECT 1 FROM pg_class c,LATERAL aclexplode(c.relacl) a WHERE c.relnamespace='public'::regnamespace AND a.grantee=role_id AND a.is_grantable)
      OR EXISTS(SELECT 1 FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid,LATERAL aclexplode(a.attacl) acl
                WHERE c.relnamespace='public'::regnamespace AND acl.grantee=role_id AND acl.is_grantable) THEN RAISE EXCEPTION 'Export grants must not be delegated'; END IF;
    IF EXISTS(SELECT 1 FROM pg_class c WHERE CASE WHEN c.relnamespace='public'::regnamespace AND c.relkind='S'
      THEN has_sequence_privilege(role_id,c.oid,'USAGE,SELECT,UPDATE') ELSE FALSE END) THEN RAISE EXCEPTION 'Export role can access sequences'; END IF;
    IF EXISTS(SELECT 1 FROM pg_proc p WHERE p.pronamespace='public'::regnamespace AND p.prosecdef
      AND p.oid NOT IN ('public.export_identity_is_current(bigint,text)'::regprocedure,'public.export_references_are_owned(text,text,text)'::regprocedure,'public.export_lock_owned(text,text)'::regprocedure)
      AND has_function_privilege(role_id,p.oid,'EXECUTE')) THEN RAISE EXCEPTION 'Export can execute unrelated privileged helper'; END IF;
  END LOOP;
  FOR fn IN SELECT p.* FROM pg_proc p WHERE p.oid IN ('public.export_identity_is_current(bigint,text)'::regprocedure,
            'public.export_references_are_owned(text,text,text)'::regprocedure,'public.export_lock_owned(text,text)'::regprocedure) LOOP
    IF fn.proowner<>'export_helper_owner'::regrole OR NOT fn.prosecdef OR fn.provolatile<>'v' OR fn.prorettype<>'boolean'::regtype
      OR fn.proisstrict IS DISTINCT FROM (fn.proname<>'export_references_are_owned')
      OR NOT fn.proconfig @> ARRAY['search_path=pg_catalog, pg_temp']
      OR NOT has_function_privilege('export_runtime',fn.oid,'EXECUTE')
      OR EXISTS(SELECT 1 FROM aclexplode(COALESCE(fn.proacl,acldefault('f',fn.proowner))) acl WHERE acl.privilege_type='EXECUTE'
        AND (acl.grantee NOT IN ('export_runtime'::regrole,'export_helper_owner'::regrole) OR (acl.grantee='export_runtime'::regrole AND acl.is_grantable))) THEN
      RAISE EXCEPTION 'Export helper owner, ACL, strictness or search path is invalid';
    END IF;
  END LOOP;
END $$;
