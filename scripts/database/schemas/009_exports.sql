CREATE TABLE IF NOT EXISTS document_exports (
    export_id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    owner_user_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT,
    conversation_id TEXT REFERENCES conversations(conversation_id) ON DELETE SET NULL,
    message_id TEXT REFERENCES conversation_messages(message_id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    format TEXT NOT NULL DEFAULT 'PDF',
    status TEXT NOT NULL DEFAULT 'COMPLETED',
    filename TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    mime_type TEXT NOT NULL DEFAULT 'application/pdf',
    file_size_bytes INTEGER NOT NULL DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
