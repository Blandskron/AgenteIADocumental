CREATE TABLE IF NOT EXISTS google_drive_connections (
    connection_id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    owner_user_id TEXT NOT NULL,
    provider_account_email TEXT,
    scopes JSONB NOT NULL DEFAULT '[]'::jsonb,
    access_token_encrypted TEXT NOT NULL,
    refresh_token_encrypted TEXT,
    expires_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS google_drive_connections_owner_unique
    ON google_drive_connections (owner_user_id);

CREATE TABLE IF NOT EXISTS google_drive_imports (
    import_id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    owner_user_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    total_files INTEGER NOT NULL DEFAULT 0,
    processed_files INTEGER NOT NULL DEFAULT 0,
    failed_files INTEGER NOT NULL DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS google_drive_import_files (
    import_file_id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    import_id TEXT NOT NULL REFERENCES google_drive_imports(import_id) ON DELETE CASCADE,
    google_file_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    export_mime_type TEXT,
    size_bytes INTEGER,
    status TEXT NOT NULL DEFAULT 'PENDING',
    document_id TEXT REFERENCES documents(document_id) ON DELETE SET NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
