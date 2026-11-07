-- Transactional bounded avatars; legacy URLs and source files are preserved for review.
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS avatar_data BYTEA;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS avatar_ready BOOLEAN NOT NULL DEFAULT FALSE;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid='user_profiles'::regclass
                   AND attname='avatar_data' AND atttypid='bytea'::regtype)
       OR NOT EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid='user_profiles'::regclass
                   AND attname='avatar_ready' AND atttypid='boolean'::regtype AND attnotnull) THEN
        RAISE EXCEPTION 'Profile avatar columns require explicit repair';
    END IF;
    IF EXISTS (SELECT 1 FROM user_profiles WHERE avatar_ready <> (avatar_data IS NOT NULL)
               OR (avatar_data IS NOT NULL AND octet_length(avatar_data) NOT BETWEEN 1 AND 1048576)) THEN
        RAISE EXCEPTION 'Profile avatar records require explicit repair';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='user_profiles'::regclass
                   AND conname='user_profiles_avatar_consistent') THEN
        ALTER TABLE user_profiles ADD CONSTRAINT user_profiles_avatar_consistent CHECK (
            avatar_ready = (avatar_data IS NOT NULL)
            AND (avatar_data IS NULL OR octet_length(avatar_data) BETWEEN 1 AND 1048576)
        );
    END IF;
END $$;
