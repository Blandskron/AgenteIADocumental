-- Read-only assertions; safe inside the provisioning transaction.
DO $$
DECLARE
    role_name text;
    role_id oid;
    col record;
    allowed boolean;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['profile_runtime','profile_identity_owner'] LOOP
        SELECT oid INTO STRICT role_id FROM pg_roles WHERE rolname=role_name
          AND NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolreplication AND NOT rolbypassrls
          AND NOT rolinherit AND rolcanlogin=(role_name='profile_runtime');
        IF EXISTS (SELECT 1 FROM pg_auth_members WHERE member=role_id)
           OR has_schema_privilege(role_id,'public','CREATE') THEN
            RAISE EXCEPTION 'Profile roles must not inherit memberships or CREATE on public';
        END IF;
        FOR col IN SELECT c.oid,c.relname,a.attnum,a.attname FROM pg_class c JOIN pg_attribute a ON a.attrelid=c.oid
          WHERE c.relnamespace='public'::regnamespace AND c.relkind IN ('r','p','v','m','f') AND a.attnum>0 AND NOT a.attisdropped LOOP
            allowed := CASE WHEN role_name='profile_runtime' THEN col.relname='user_profiles'
              ELSE col.relname='auth_user' AND col.attname IN ('id','is_active','password') END;
            IF has_column_privilege(role_id,col.oid,col.attnum,'SELECT') IS DISTINCT FROM allowed THEN
                RAISE EXCEPTION 'Profile role exceeds allowed read columns';
            END IF;
            allowed := role_name='profile_runtime' AND col.relname='user_profiles'
              AND col.attname IN ('user_id','email','phone_number','profile_picture_url','additional_info','avatar_data','avatar_ready');
            IF has_column_privilege(role_id,col.oid,col.attnum,'INSERT') IS DISTINCT FROM allowed THEN
                RAISE EXCEPTION 'Profile role exceeds allowed insert columns';
            END IF;
            allowed := CASE WHEN role_name='profile_identity_owner' THEN col.relname='auth_user' AND col.attname='id'
              ELSE col.relname='user_profiles' AND col.attname IN ('email','phone_number','profile_picture_url','additional_info','version','avatar_data','avatar_ready') END;
            IF has_column_privilege(role_id,col.oid,col.attnum,'UPDATE') IS DISTINCT FROM allowed THEN
                RAISE EXCEPTION 'Profile role exceeds allowed update columns';
            END IF;
            IF has_column_privilege(role_id,col.oid,col.attnum,'REFERENCES')
               OR has_table_privilege(role_id,col.oid,'DELETE,TRUNCATE,TRIGGER') THEN
                RAISE EXCEPTION 'Profile role exceeds allowed table operations';
            END IF;
        END LOOP;
        IF EXISTS (SELECT 1 FROM pg_class c,LATERAL aclexplode(c.relacl) acl
            WHERE c.relnamespace='public'::regnamespace AND acl.grantee=role_id AND acl.is_grantable)
           OR EXISTS (SELECT 1 FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid,LATERAL aclexplode(a.attacl) acl
            WHERE c.relnamespace='public'::regnamespace AND acl.grantee=role_id AND acl.is_grantable) THEN
            RAISE EXCEPTION 'Profile roles must not delegate table or column privileges';
        END IF;
        IF EXISTS (SELECT 1 FROM pg_class c WHERE CASE WHEN c.relnamespace='public'::regnamespace AND c.relkind='S'
            THEN has_sequence_privilege(role_id,c.oid,'USAGE,SELECT,UPDATE') ELSE FALSE END) THEN
            RAISE EXCEPTION 'Profile roles must not access application sequences';
        END IF;
        IF EXISTS (SELECT 1 FROM pg_proc p WHERE p.pronamespace='public'::regnamespace AND p.prosecdef
            AND p.oid<>'public.profile_identity_is_current(bigint,text)'::regprocedure
            AND has_function_privilege(role_id,p.oid,'EXECUTE')) THEN
            RAISE EXCEPTION 'Profile role can execute another privileged helper';
        END IF;
    END LOOP;
    IF NOT EXISTS (SELECT 1 FROM pg_proc WHERE oid='public.profile_identity_is_current(bigint,text)'::regprocedure
        AND proowner='profile_identity_owner'::regrole AND prosecdef AND proisstrict AND provolatile='v'
        AND prorettype='boolean'::regtype AND proconfig @> ARRAY['search_path=pg_catalog, pg_temp'])
       OR NOT has_function_privilege('profile_runtime','public.profile_identity_is_current(bigint,text)','EXECUTE')
       OR EXISTS (SELECT 1 FROM pg_proc p,LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) acl
          WHERE p.oid='public.profile_identity_is_current(bigint,text)'::regprocedure AND acl.privilege_type='EXECUTE'
            AND (acl.grantee NOT IN ('profile_identity_owner'::regrole,'profile_runtime'::regrole)
                 OR (acl.grantee='profile_runtime'::regrole AND acl.is_grantable))) THEN
        RAISE EXCEPTION 'Profile identity function owner, search path or ACL is invalid';
    END IF;
END $$;
