-- Aggregate-only preflight; never print contacts, metadata or identifiers.
DO $$
DECLARE noncanonical bigint; orphaned bigint; nonobjects bigint;
BEGIN
    SELECT count(*) INTO noncanonical FROM user_profiles
    WHERE CASE WHEN user_id ~ '^[1-9][0-9]{0,18}$'
               THEN user_id::numeric > 9223372036854775807 ELSE TRUE END;
    RAISE NOTICE 'Profile preflight: noncanonical identities=% (preserved)', noncanonical;
    SELECT count(*) INTO nonobjects FROM user_profiles WHERE jsonb_typeof(additional_info) <> 'object';
    RAISE NOTICE 'Profile preflight: nonobject metadata=% (preserved; explicit repair required)', nonobjects;
    IF to_regclass('public.auth_user') IS NOT NULL THEN
        SELECT count(*) INTO orphaned FROM user_profiles p
        WHERE NOT EXISTS (SELECT 1 FROM public.auth_user u WHERE u.id::text = p.user_id);
        RAISE NOTICE 'Profile preflight: unmatched identities=% (preserved; PLAT-001)', orphaned;
    ELSE
        RAISE NOTICE 'Profile preflight: Auth migrations pending; identity audit deferred';
    END IF;
END $$;
