-- Called by the development HTTP probe coordinator, never by the API.
BEGIN;
SELECT set_config('profile.probe_marker', :'probe_marker', TRUE) AS marker \gset
DO $$
BEGIN
    IF current_setting('profile.probe_marker') !~ '^[0-9a-f]{32}$' THEN
        RAISE EXCEPTION 'Invalid synthetic probe marker';
    END IF;
END $$;
DELETE FROM user_profiles p
WHERE p.additional_info->>'profile_probe' = current_setting('profile.probe_marker')
  AND NOT EXISTS (SELECT 1 FROM auth_user u WHERE u.id::text=p.user_id);
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM user_profiles WHERE additional_info->>'profile_probe'=current_setting('profile.probe_marker')) THEN
        RAISE EXCEPTION 'Synthetic probe cleanup is incomplete';
    END IF;
END $$;
COMMIT;
