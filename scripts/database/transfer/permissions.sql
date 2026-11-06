GRANT USAGE ON SCHEMA public TO document_transfer_runtime, document_transfer_reference_owner;
REVOKE CREATE ON SCHEMA public FROM document_transfer_runtime, document_transfer_reference_owner;

GRANT SELECT ON public.transfer_events TO document_transfer_runtime;
GRANT INSERT (owner_user_id, document_id, filename, direction, status, progress, size_bytes, metadata)
    ON public.transfer_events TO document_transfer_runtime;
GRANT UPDATE (document_id, status, progress, size_bytes, metadata, updated_at)
    ON public.transfer_events TO document_transfer_runtime;
GRANT DELETE ON public.transfer_events TO document_transfer_runtime;
GRANT SELECT (document_id, tenant_id, owner_user_id, metadata) ON public.documents TO document_transfer_runtime;
GRANT SELECT (assignment_id, document_id, assigned_to_user_id, assigned_by_user_id, status)
    ON public.document_assignments TO document_transfer_runtime;

-- Only a non-login owner can lock a document reference, without a general write helper.
GRANT SELECT (document_id), UPDATE (document_id) ON public.documents TO document_transfer_reference_owner;
CREATE OR REPLACE FUNCTION public.transfer_lock_document_reference(identifier text)
RETURNS boolean LANGUAGE plpgsql VOLATILE STRICT SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    PERFORM 1 FROM public.documents AS d WHERE d.document_id = identifier FOR KEY SHARE OF d;
    RETURN FOUND;
END
$$;
ALTER FUNCTION public.transfer_lock_document_reference(text) OWNER TO document_transfer_reference_owner;
REVOKE ALL ON FUNCTION public.transfer_lock_document_reference(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.transfer_lock_document_reference(text) TO document_transfer_runtime;
