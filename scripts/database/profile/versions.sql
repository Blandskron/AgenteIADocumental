-- Additive, idempotent upgrade: preserve all existing ownership and field values.
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS version BIGINT NOT NULL DEFAULT 1;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid = 'user_profiles'::regclass
                   AND attname = 'version' AND atttypid = 'bigint'::regtype AND attnotnull) THEN
        RAISE EXCEPTION 'Profile version column requires explicit repair';
    END IF;
    IF EXISTS (SELECT 1 FROM user_profiles WHERE version < 1 OR version IS NULL) THEN
        RAISE EXCEPTION 'Profile versions require explicit repair';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conrelid = 'user_profiles'::regclass AND conname = 'user_profiles_version_positive') THEN
        ALTER TABLE user_profiles ADD CONSTRAINT user_profiles_version_positive CHECK (version >= 1);
    END IF;
END $$;
