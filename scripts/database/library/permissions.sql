-- Called by provisioning or an isolated test database after the roles exist.
GRANT USAGE ON SCHEMA public TO document_library_runtime, document_library_reference_owner;
REVOKE CREATE ON SCHEMA public FROM document_library_runtime, document_library_reference_owner;

GRANT SELECT (document_id, tenant_id, owner_user_id, owner_area_id, created_by_user_id,
    filename, mime_type, status, metadata, created_at, updated_at) ON public.documents TO document_library_runtime;
GRANT SELECT (document_id, assigned_to_user_id, assigned_by_user_id, status)
    ON public.document_assignments TO document_library_runtime;
GRANT SELECT (chunk_id, document_id) ON public.document_embeddings TO document_library_runtime;
GRANT SELECT, INSERT, DELETE ON public.document_folders, public.document_folder_items, public.document_favorites
    TO document_library_runtime;
GRANT UPDATE (name, metadata, updated_at) ON public.document_folders TO document_library_runtime;

-- Only this non-login owner can acquire document row locks. No generic write helper.
GRANT SELECT (document_id), UPDATE (document_id) ON public.documents TO document_library_reference_owner;
CREATE OR REPLACE FUNCTION public.library_lock_document_reference(identifier text)
RETURNS boolean LANGUAGE plpgsql VOLATILE STRICT SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    PERFORM 1 FROM public.documents AS d WHERE d.document_id = identifier FOR KEY SHARE OF d;
    RETURN FOUND;
END
$$;
ALTER FUNCTION public.library_lock_document_reference(text) OWNER TO document_library_reference_owner;
REVOKE ALL ON FUNCTION public.library_lock_document_reference(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.library_lock_document_reference(text) TO document_library_runtime;
