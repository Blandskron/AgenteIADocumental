CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    tenant_id TEXT REFERENCES tenants(tenant_id) ON DELETE SET NULL,
    owner_user_id TEXT,
    owner_area_id TEXT REFERENCES tenant_areas(area_id) ON DELETE SET NULL,
    created_by_user_id TEXT,
    document_type TEXT NOT NULL DEFAULT 'INFORMATIVE',
    visibility TEXT NOT NULL DEFAULT 'PRIVATE',
    requires_approval BOOLEAN NOT NULL DEFAULT FALSE,
    requires_rejection BOOLEAN NOT NULL DEFAULT FALSE,
    requires_signature BOOLEAN NOT NULL DEFAULT FALSE,
    allow_download BOOLEAN NOT NULL DEFAULT TRUE,
    expires_at TIMESTAMPTZ,
    filename TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    processing_error TEXT,
    processed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS tenant_id TEXT REFERENCES tenants(tenant_id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS owner_user_id TEXT,
    ADD COLUMN IF NOT EXISTS owner_area_id TEXT REFERENCES tenant_areas(area_id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS created_by_user_id TEXT,
    ADD COLUMN IF NOT EXISTS document_type TEXT NOT NULL DEFAULT 'INFORMATIVE',
    ADD COLUMN IF NOT EXISTS visibility TEXT NOT NULL DEFAULT 'PRIVATE',
    ADD COLUMN IF NOT EXISTS requires_approval BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS requires_rejection BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS requires_signature BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS allow_download BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;

UPDATE documents
SET
    tenant_id = COALESCE(
        tenant_id,
        CASE
            WHEN EXISTS (SELECT 1 FROM tenants WHERE tenants.tenant_id = NULLIF(documents.metadata->>'tenant_id', ''))
            THEN NULLIF(metadata->>'tenant_id', '')
            ELSE NULL
        END
    ),
    owner_user_id = COALESCE(owner_user_id, NULLIF(metadata->>'owner_user_id', '')),
    created_by_user_id = COALESCE(created_by_user_id, NULLIF(metadata->>'owner_user_id', ''))
WHERE tenant_id IS NULL
   OR owner_user_id IS NULL
   OR created_by_user_id IS NULL;

CREATE TABLE IF NOT EXISTS document_embeddings (
    chunk_id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    chunk_content TEXT NOT NULL,
    embedding vector(384) NOT NULL,
    embedding_model TEXT NOT NULL DEFAULT 'intfloat/multilingual-e5-small',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS document_folders (
    folder_id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    name TEXT NOT NULL,
    parent_folder_id TEXT REFERENCES document_folders(folder_id) ON DELETE CASCADE,
    owner_user_id TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS document_folder_items (
    folder_id TEXT NOT NULL REFERENCES document_folders(folder_id) ON DELETE CASCADE,
    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    owner_user_id TEXT NOT NULL,
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (folder_id, document_id)
);

CREATE TABLE IF NOT EXISTS document_favorites (
    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    owner_user_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (document_id, owner_user_id)
);

CREATE TABLE IF NOT EXISTS transfer_events (
    transfer_id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    owner_user_id TEXT NOT NULL,
    document_id TEXT REFERENCES documents(document_id) ON DELETE SET NULL,
    filename TEXT NOT NULL,
    direction TEXT NOT NULL,
    status TEXT NOT NULL,
    progress INTEGER NOT NULL DEFAULT 0,
    size_bytes BIGINT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS document_assignments (
    assignment_id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    assigned_to_user_id TEXT NOT NULL,
    assigned_by_user_id TEXT NOT NULL,
    assigned_by_role TEXT,
    status TEXT NOT NULL DEFAULT 'PENDING',
    allow_download BOOLEAN NOT NULL DEFAULT TRUE,
    rejection_reason TEXT,
    signature_value TEXT,
    signed_at TIMESTAMPTZ,
    due_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT document_assignments_status_check CHECK (status IN ('PENDING', 'VIEWED', 'ACCEPTED', 'REJECTED', 'SIGNED', 'EXPIRED', 'CANCELLED')),
    CONSTRAINT document_assignments_unique_user_document UNIQUE (document_id, assigned_to_user_id)
);

ALTER TABLE document_assignments
    ADD COLUMN IF NOT EXISTS allow_download BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE document_assignments
    DROP CONSTRAINT IF EXISTS document_assignments_status_check;

ALTER TABLE document_assignments
    ADD CONSTRAINT document_assignments_status_check CHECK (status IN ('PENDING', 'VIEWED', 'ACCEPTED', 'REJECTED', 'SIGNED', 'EXPIRED', 'CANCELLED'));

CREATE TABLE IF NOT EXISTS document_assignment_events (
    event_id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    assignment_id TEXT NOT NULL REFERENCES document_assignments(assignment_id) ON DELETE CASCADE,
    actor_user_id TEXT NOT NULL,
    action TEXT NOT NULL,
    reason TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT document_assignment_events_action_check CHECK (action IN ('ASSIGNED', 'VIEWED', 'DOWNLOADED', 'ACCEPTED', 'REJECTED', 'SIGNED', 'EXPIRED', 'CANCELLED'))
);

ALTER TABLE document_assignment_events
    DROP CONSTRAINT IF EXISTS document_assignment_events_action_check;

ALTER TABLE document_assignment_events
    ADD CONSTRAINT document_assignment_events_action_check CHECK (action IN ('ASSIGNED', 'VIEWED', 'DOWNLOADED', 'ACCEPTED', 'REJECTED', 'SIGNED', 'EXPIRED', 'CANCELLED'));
