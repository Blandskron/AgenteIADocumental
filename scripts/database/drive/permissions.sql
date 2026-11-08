GRANT SELECT, DELETE ON public.google_drive_oauth_attempts TO drive_runtime;
GRANT INSERT (state_hash,owner_user_id,identity_binding,configuration_hash,code_challenge,connection_version,expires_at) ON public.google_drive_oauth_attempts TO drive_runtime;
GRANT UPDATE (consumed_at) ON public.google_drive_oauth_attempts TO drive_runtime;
GRANT USAGE ON SCHEMA public TO drive_runtime, drive_helper_owner;
REVOKE CREATE ON SCHEMA public FROM drive_runtime, drive_helper_owner;
GRANT SELECT ON public.google_drive_connections TO drive_runtime;
GRANT INSERT (owner_user_id,version,grant_status,provider_account_id,oauth_client_id,lease_token,lease_until,lease_kind,provider_account_email,scopes,access_token_encrypted,refresh_token_encrypted,expires_at,metadata) ON public.google_drive_connections TO drive_runtime;
GRANT UPDATE (version,grant_status,provider_account_id,oauth_client_id,lease_token,lease_until,lease_kind,provider_account_email,scopes,access_token_encrypted,refresh_token_encrypted,expires_at,metadata,updated_at) ON public.google_drive_connections TO drive_runtime;
GRANT SELECT ON public.google_drive_imports TO drive_runtime;
GRANT INSERT (owner_user_id,status,total_files,processed_files,failed_files,metadata,error_message) ON public.google_drive_imports TO drive_runtime;
GRANT UPDATE (processed_files,failed_files,status,error_message,updated_at) ON public.google_drive_imports TO drive_runtime;
GRANT SELECT ON public.google_drive_import_files TO drive_runtime;
GRANT INSERT (import_id,google_file_id,filename,mime_type,export_mime_type,size_bytes,status,document_id,metadata,error_message) ON public.google_drive_import_files TO drive_runtime;
GRANT UPDATE (filename,mime_type,export_mime_type,size_bytes,status,document_id,metadata,error_message,updated_at) ON public.google_drive_import_files TO drive_runtime;
GRANT SELECT (id,is_active,password,is_superuser) ON public.auth_user TO drive_helper_owner;
GRANT SELECT (tenant_id,status) ON public.tenants TO drive_helper_owner;
GRANT SELECT (tenant_id,user_id,status) ON public.tenant_memberships TO drive_helper_owner;
GRANT SELECT (tenant_id,user_id,group_id) ON public.tenant_user_groups TO drive_helper_owner;
GRANT SELECT (group_id,tenant_id) ON public.tenant_groups TO drive_helper_owner;
GRANT SELECT (group_id,permission_code) ON public.tenant_group_permissions TO drive_helper_owner;
GRANT SELECT (document_id,owner_user_id) ON public.documents TO drive_helper_owner;
GRANT SELECT (folder_id,parent_folder_id,owner_user_id) ON public.document_folders TO drive_helper_owner;
GRANT SELECT (folder_id,document_id) ON public.document_folder_items TO drive_helper_owner;
GRANT UPDATE (id) ON public.auth_user TO drive_helper_owner;
GRANT UPDATE (document_id) ON public.documents TO drive_helper_owner;
GRANT UPDATE (folder_id) ON public.document_folders TO drive_helper_owner;
GRANT INSERT (folder_id,document_id,owner_user_id) ON public.document_folder_items TO drive_helper_owner;

CREATE OR REPLACE FUNCTION public.drive_identity_is_current(identifier bigint,fingerprint text)
RETURNS boolean LANGUAGE plpgsql VOLATILE STRICT SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
BEGIN
    RETURN EXISTS(SELECT 1 FROM public.auth_user u WHERE u.id=identifier AND u.is_active IS TRUE
                  AND upper(md5(u.password))=fingerprint FOR SHARE OF u);
END $$;

CREATE OR REPLACE FUNCTION public.drive_access_is_allowed(identifier bigint,requested_tenant text)
RETURNS boolean LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
    SELECT EXISTS(SELECT 1 FROM public.auth_user u WHERE u.id=identifier AND u.is_active IS TRUE AND
      (u.is_superuser IS TRUE OR EXISTS(
        SELECT 1 FROM public.tenant_memberships m JOIN public.tenants t ON t.tenant_id=m.tenant_id
        JOIN public.tenant_user_groups ug ON ug.user_id=m.user_id AND ug.tenant_id=m.tenant_id
        JOIN public.tenant_groups g ON g.group_id=ug.group_id AND g.tenant_id=ug.tenant_id
        JOIN public.tenant_group_permissions p ON p.group_id=g.group_id
        WHERE m.user_id=identifier::text AND m.tenant_id=requested_tenant AND m.status='ACTIVE' AND t.status='ACTIVE'
          AND p.permission_code IN ('use_google_drive','*'))));
$$;

CREATE OR REPLACE FUNCTION public.drive_owns_folder(folder text,requested_owner text)
RETURNS boolean LANGUAGE sql VOLATILE STRICT SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
    SELECT EXISTS(SELECT 1 FROM public.document_folders f WHERE f.folder_id=folder AND f.owner_user_id=requested_owner);
$$;

CREATE OR REPLACE FUNCTION public.drive_associate_document(folder text,document text,requested_owner text)
RETURNS boolean LANGUAGE plpgsql VOLATILE STRICT SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE ancestors text[];
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended('blandskron.library.document:'||requested_owner||':'||document,0));
    PERFORM 1 FROM public.documents d WHERE d.document_id=document AND d.owner_user_id=requested_owner FOR KEY SHARE OF d;
    IF NOT FOUND THEN RETURN FALSE; END IF;
    SELECT array_agg(locked.folder_id) INTO ancestors FROM (
        WITH RECURSIVE ancestry AS (
          SELECT f.folder_id,f.parent_folder_id,0 AS depth FROM public.document_folders f
          WHERE f.folder_id=folder AND f.owner_user_id=requested_owner
          UNION ALL
          SELECT p.folder_id,p.parent_folder_id,a.depth+1 FROM public.document_folders p JOIN ancestry a
          ON p.folder_id=a.parent_folder_id WHERE p.owner_user_id=requested_owner)
        SELECT f.folder_id FROM public.document_folders f JOIN ancestry a ON a.folder_id=f.folder_id
        ORDER BY a.depth DESC FOR KEY SHARE OF f
    ) locked;
    IF ancestors IS NULL OR NOT folder=ANY(ancestors) THEN RETURN FALSE; END IF;
    INSERT INTO public.document_folder_items(folder_id,document_id,owner_user_id)
        VALUES(folder,document,requested_owner) ON CONFLICT(folder_id,document_id) DO NOTHING;
    RETURN TRUE;
EXCEPTION WHEN foreign_key_violation THEN RETURN FALSE;
END $$;
ALTER FUNCTION public.drive_identity_is_current(bigint,text) OWNER TO drive_helper_owner;
REVOKE ALL ON FUNCTION public.drive_identity_is_current(bigint,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.drive_identity_is_current(bigint,text) TO drive_runtime;
ALTER FUNCTION public.drive_access_is_allowed(bigint,text) OWNER TO drive_helper_owner;
REVOKE ALL ON FUNCTION public.drive_access_is_allowed(bigint,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.drive_access_is_allowed(bigint,text) TO drive_runtime;
ALTER FUNCTION public.drive_owns_folder(text,text) OWNER TO drive_helper_owner;
REVOKE ALL ON FUNCTION public.drive_owns_folder(text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.drive_owns_folder(text,text) TO drive_runtime;
ALTER FUNCTION public.drive_associate_document(text,text,text) OWNER TO drive_helper_owner;
REVOKE ALL ON FUNCTION public.drive_associate_document(text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.drive_associate_document(text,text,text) TO drive_runtime;
