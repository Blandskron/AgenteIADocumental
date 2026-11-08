GRANT USAGE ON SCHEMA public TO export_runtime, export_helper_owner;
REVOKE CREATE ON SCHEMA public FROM export_runtime, export_helper_owner;
GRANT SELECT (export_id,owner_user_id,source_type,source_id,conversation_id,message_id,title,format,status,filename,mime_type,
              file_size_bytes,metadata,created_at,updated_at,pdf_data,pdf_sha256,expires_at,operation_key,request_sha256)
    ON public.document_exports TO export_runtime;
GRANT DELETE ON public.document_exports TO export_runtime;
GRANT INSERT (owner_user_id,source_type,source_id,conversation_id,message_id,title,format,status,filename,storage_path,
              mime_type,file_size_bytes,metadata,error_message,pdf_data,pdf_sha256,expires_at,operation_key,request_sha256)
    ON public.document_exports TO export_runtime;
GRANT SELECT (id,is_active,password), UPDATE(id) ON public.auth_user TO export_helper_owner;
GRANT SELECT (conversation_id,owner_user_id), UPDATE(conversation_id) ON public.conversations TO export_helper_owner;
GRANT SELECT (message_id,conversation_id,owner_user_id), UPDATE(message_id) ON public.conversation_messages TO export_helper_owner;
GRANT SELECT (export_id,owner_user_id), UPDATE(export_id) ON public.document_exports TO export_helper_owner;

CREATE OR REPLACE FUNCTION public.export_identity_is_current(identifier bigint,fingerprint text)
RETURNS boolean LANGUAGE plpgsql VOLATILE STRICT SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
BEGIN
    RETURN EXISTS (SELECT 1 FROM public.auth_user u WHERE u.id=identifier AND u.is_active IS TRUE
                   AND upper(md5(u.password))=fingerprint FOR SHARE OF u);
END $$;
CREATE OR REPLACE FUNCTION public.export_references_are_owned(requested_owner text,conversation text,message text)
RETURNS boolean LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
BEGIN
    IF requested_owner IS NULL THEN RETURN FALSE; END IF;
    IF conversation IS NOT NULL THEN
        PERFORM 1 FROM public.conversations c WHERE c.conversation_id=conversation AND c.owner_user_id=requested_owner FOR SHARE OF c;
        IF NOT FOUND THEN RETURN FALSE; END IF;
    END IF;
    IF message IS NOT NULL THEN
        PERFORM 1 FROM public.conversation_messages m JOIN public.conversations c ON c.conversation_id=m.conversation_id
        WHERE m.message_id=message AND m.owner_user_id=requested_owner AND c.owner_user_id=requested_owner
          AND (conversation IS NULL OR m.conversation_id=conversation) FOR SHARE OF c,m;
        IF NOT FOUND THEN RETURN FALSE; END IF;
    END IF;
    RETURN TRUE;
END $$;
CREATE OR REPLACE FUNCTION public.export_lock_owned(identifier text,requested_owner text)
RETURNS boolean LANGUAGE plpgsql VOLATILE STRICT SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
BEGIN
    RETURN EXISTS (SELECT 1 FROM public.document_exports e WHERE e.export_id=identifier AND e.owner_user_id=requested_owner FOR SHARE OF e);
END $$;
ALTER FUNCTION public.export_identity_is_current(bigint,text) OWNER TO export_helper_owner;
ALTER FUNCTION public.export_references_are_owned(text,text,text) OWNER TO export_helper_owner;
ALTER FUNCTION public.export_lock_owned(text,text) OWNER TO export_helper_owner;
REVOKE ALL ON FUNCTION public.export_identity_is_current(bigint,text),public.export_references_are_owned(text,text,text),public.export_lock_owned(text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.export_identity_is_current(bigint,text),public.export_references_are_owned(text,text,text),public.export_lock_owned(text,text) TO export_runtime;
