CREATE TABLE IF NOT EXISTS user_profiles (
    profile_id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id TEXT NOT NULL UNIQUE, -- Django User ID
    email TEXT,
    phone_number TEXT,
    profile_picture_url TEXT,
    additional_info JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
