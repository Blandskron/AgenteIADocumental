DO $$
DECLARE role_name text; role_id oid; col record; allowed boolean; fn record;
BEGIN
  FOREACH role_name IN ARRAY ARRAY['drive_runtime','drive_helper_owner'] LOOP
    SELECT oid INTO STRICT role_id FROM pg_roles WHERE rolname=role_name AND NOT rolsuper AND NOT rolcreatedb
      AND NOT rolcreaterole AND NOT rolreplication AND NOT rolbypassrls AND NOT rolinherit AND rolcanlogin=(role_name='drive_runtime');
    IF EXISTS(SELECT 1 FROM pg_auth_members WHERE member=role_id) OR has_schema_privilege(role_id,'public','CREATE') THEN
      RAISE EXCEPTION 'Drive role has memberships or schema CREATE';
    END IF;
    FOR col IN SELECT c.oid,c.relname,a.attnum,a.attname FROM pg_class c JOIN pg_attribute a ON a.attrelid=c.oid
      WHERE c.relnamespace='public'::regnamespace AND c.relkind IN ('r','p','v','m','f') AND a.attnum>0 AND NOT a.attisdropped LOOP
      allowed := CASE WHEN role_name='drive_runtime' THEN col.relname IN ('google_drive_connections','google_drive_imports','google_drive_import_files','google_drive_oauth_attempts')
        ELSE (col.relname='auth_user' AND col.attname IN ('id','is_active','password','is_superuser')) OR (col.relname='tenants' AND col.attname IN ('tenant_id','status')) OR (col.relname='tenant_memberships' AND col.attname IN ('tenant_id','user_id','status')) OR (col.relname='tenant_user_groups' AND col.attname IN ('tenant_id','user_id','group_id')) OR (col.relname='tenant_groups' AND col.attname IN ('group_id','tenant_id')) OR (col.relname='tenant_group_permissions' AND col.attname IN ('group_id','permission_code')) OR (col.relname='documents' AND col.attname IN ('document_id','owner_user_id')) OR (col.relname='document_folders' AND col.attname IN ('folder_id','parent_folder_id','owner_user_id')) OR (col.relname='document_folder_items' AND col.attname IN ('folder_id','document_id')) END;
      IF has_column_privilege(role_id,col.oid,col.attnum,'SELECT') IS DISTINCT FROM allowed THEN RAISE EXCEPTION 'Drive SELECT exceeds allowed columns'; END IF;
      allowed := CASE WHEN role_name='drive_runtime' THEN (col.relname='google_drive_oauth_attempts' AND col.attname IN ('state_hash','owner_user_id','identity_binding','configuration_hash','code_challenge','connection_version','expires_at')) OR (col.relname='google_drive_connections' AND col.attname IN ('owner_user_id','version','grant_status','provider_account_id','oauth_client_id','lease_token','lease_until','lease_kind','provider_account_email','scopes','access_token_encrypted','refresh_token_encrypted','expires_at','metadata')) OR (col.relname='google_drive_imports' AND col.attname IN ('owner_user_id','status','total_files','processed_files','failed_files','metadata','error_message')) OR (col.relname='google_drive_import_files' AND col.attname IN ('import_id','google_file_id','filename','mime_type','export_mime_type','size_bytes','status','document_id','metadata','error_message')) ELSE col.relname='document_folder_items' AND col.attname IN ('folder_id','document_id','owner_user_id') END;
      IF has_column_privilege(role_id,col.oid,col.attnum,'INSERT') IS DISTINCT FROM allowed THEN RAISE EXCEPTION 'Drive INSERT exceeds allowed columns'; END IF;
      allowed := CASE WHEN role_name='drive_runtime' THEN (col.relname='google_drive_oauth_attempts' AND col.attname='consumed_at') OR (col.relname='google_drive_connections' AND col.attname IN ('version','grant_status','provider_account_id','oauth_client_id','lease_token','lease_until','lease_kind','provider_account_email','scopes','access_token_encrypted','refresh_token_encrypted','expires_at','metadata','updated_at')) OR (col.relname='google_drive_imports' AND col.attname IN ('processed_files','failed_files','status','error_message','updated_at')) OR (col.relname='google_drive_import_files' AND col.attname IN ('filename','mime_type','export_mime_type','size_bytes','status','document_id','metadata','error_message','updated_at')) ELSE
        (col.relname='auth_user' AND col.attname='id') OR (col.relname='documents' AND col.attname='document_id')
        OR (col.relname='document_folders' AND col.attname='folder_id') END;
      IF has_column_privilege(role_id,col.oid,col.attnum,'UPDATE') IS DISTINCT FROM allowed THEN RAISE EXCEPTION 'Drive UPDATE exceeds allowed columns'; END IF;
      IF has_table_privilege(role_id,col.oid,'DELETE') IS DISTINCT FROM (role_name='drive_runtime' AND col.relname='google_drive_oauth_attempts') OR has_table_privilege(role_id,col.oid,'TRUNCATE,TRIGGER') OR has_column_privilege(role_id,col.oid,col.attnum,'REFERENCES') THEN RAISE EXCEPTION 'Drive destructive privilege'; END IF;
    END LOOP;
    IF EXISTS(SELECT 1 FROM pg_class c,LATERAL aclexplode(c.relacl) a WHERE c.relnamespace='public'::regnamespace AND a.grantee=role_id AND a.is_grantable)
      OR EXISTS(SELECT 1 FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid,LATERAL aclexplode(a.attacl) acl WHERE c.relnamespace='public'::regnamespace AND acl.grantee=role_id AND acl.is_grantable) THEN RAISE EXCEPTION 'Drive grants must not be delegated'; END IF;
    IF EXISTS(SELECT 1 FROM pg_class c WHERE CASE WHEN c.relnamespace='public'::regnamespace AND c.relkind='S'
      THEN has_sequence_privilege(role_id,c.oid,'USAGE,SELECT,UPDATE') ELSE FALSE END) THEN RAISE EXCEPTION 'Drive sequence access'; END IF;
    IF EXISTS(SELECT 1 FROM pg_proc p WHERE p.pronamespace='public'::regnamespace AND p.prosecdef AND p.oid NOT IN ('public.drive_identity_is_current(bigint,text)'::regprocedure,'public.drive_access_is_allowed(bigint,text)'::regprocedure,'public.drive_owns_folder(text,text)'::regprocedure,'public.drive_associate_document(text,text,text)'::regprocedure)
      AND has_function_privilege(role_id,p.oid,'EXECUTE')) THEN RAISE EXCEPTION 'Drive unrelated privileged helper'; END IF;
  END LOOP;
  FOR fn IN SELECT p.* FROM pg_proc p WHERE p.oid IN ('public.drive_identity_is_current(bigint,text)'::regprocedure,'public.drive_access_is_allowed(bigint,text)'::regprocedure,'public.drive_owns_folder(text,text)'::regprocedure,'public.drive_associate_document(text,text,text)'::regprocedure) LOOP
    IF fn.proowner<>'drive_helper_owner'::regrole OR NOT fn.prosecdef OR fn.provolatile<>'v' OR fn.prorettype<>'boolean'::regtype
      OR fn.proisstrict IS DISTINCT FROM (fn.proname<>'drive_access_is_allowed')
      OR NOT fn.proconfig @> ARRAY['search_path=pg_catalog, pg_temp']
      OR NOT has_function_privilege('drive_runtime',fn.oid,'EXECUTE')
      OR EXISTS(SELECT 1 FROM aclexplode(COALESCE(fn.proacl,acldefault('f',fn.proowner))) acl WHERE acl.privilege_type='EXECUTE'
        AND (acl.grantee NOT IN ('drive_runtime'::regrole,'drive_helper_owner'::regrole) OR (acl.grantee='drive_runtime'::regrole AND acl.is_grantable))) THEN
      RAISE EXCEPTION 'Drive helper owner, ACL, signature or search path is invalid';
    END IF;
  END LOOP;
END $$;
