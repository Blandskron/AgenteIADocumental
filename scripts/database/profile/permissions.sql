GRANT USAGE ON SCHEMA public TO profile_runtime, profile_identity_owner;
REVOKE CREATE ON SCHEMA public FROM profile_runtime, profile_identity_owner;
GRANT SELECT ON public.user_profiles TO profile_runtime;
GRANT INSERT (user_id,email,phone_number,profile_picture_url,additional_info,avatar_data,avatar_ready)
    ON public.user_profiles TO profile_runtime;
GRANT UPDATE (email,phone_number,profile_picture_url,additional_info,version,avatar_data,avatar_ready)
    ON public.user_profiles TO profile_runtime;

-- The non-login owner can check and lock identity; runtime never reads encoded passwords.
GRANT SELECT (id,is_active,password), UPDATE (id) ON public.auth_user TO profile_identity_owner;
CREATE OR REPLACE FUNCTION public.profile_identity_is_current(identifier bigint, fingerprint text)
RETURNS boolean LANGUAGE plpgsql VOLATILE STRICT SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM public.auth_user AS u
        WHERE u.id=identifier AND u.is_active IS TRUE AND upper(md5(u.password))=fingerprint
        FOR SHARE OF u
    );
END
$$;
ALTER FUNCTION public.profile_identity_is_current(bigint,text) OWNER TO profile_identity_owner;
REVOKE ALL ON FUNCTION public.profile_identity_is_current(bigint,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.profile_identity_is_current(bigint,text) TO profile_runtime;
