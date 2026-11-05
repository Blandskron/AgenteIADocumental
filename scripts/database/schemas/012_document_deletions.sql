CREATE TABLE IF NOT EXISTS document_deletions (
    document_id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    owner_user_id TEXT,
    tenant_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    file_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_error TEXT
);

CREATE INDEX IF NOT EXISTS document_deletions_pending_idx
    ON document_deletions (next_attempt_at, document_id)
    WHERE completed_at IS NULL;
