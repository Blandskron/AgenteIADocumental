-- Knowledge Studio P0 isolated schema (`studio.*`) — R4-01.
-- Reversible via: DROP SCHEMA IF EXISTS studio CASCADE;

CREATE SCHEMA IF NOT EXISTS studio;

CREATE TABLE IF NOT EXISTS studio.collections (
    collection_id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    tenant_id TEXT NOT NULL REFERENCES public.tenants(tenant_id) ON DELETE CASCADE,
    owner_user_id TEXT NOT NULL,
    area_id TEXT REFERENCES public.tenant_areas(area_id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    visibility TEXT NOT NULL DEFAULT 'private',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT studio_collections_visibility_check CHECK (visibility IN ('private', 'area', 'company'))
);

CREATE TABLE IF NOT EXISTS studio.collection_documents (
    collection_id TEXT NOT NULL REFERENCES studio.collections(collection_id) ON DELETE CASCADE,
    document_id TEXT NOT NULL REFERENCES public.documents(document_id) ON DELETE CASCADE,
    content_sha256 TEXT,
    added_by_user_id TEXT NOT NULL,
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (collection_id, document_id)
);

CREATE TABLE IF NOT EXISTS studio.studio_jobs (
    job_id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    tenant_id TEXT NOT NULL REFERENCES public.tenants(tenant_id) ON DELETE CASCADE,
    collection_id TEXT NOT NULL REFERENCES studio.collections(collection_id) ON DELETE CASCADE,
    created_by_user_id TEXT NOT NULL,
    operation_key TEXT NOT NULL,
    template_id TEXT NOT NULL,
    template_version TEXT NOT NULL DEFAULT '1.0.0',
    model_id TEXT,
    options JSONB NOT NULL DEFAULT '{}'::jsonb,
    cache_fingerprint TEXT,
    status TEXT NOT NULL DEFAULT 'PENDING',
    step TEXT NOT NULL DEFAULT 'queued',
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 2,
    cancel_requested BOOLEAN NOT NULL DEFAULT FALSE,
    heartbeat_at TIMESTAMPTZ,
    error_code TEXT,
    error_message TEXT,
    usage_tokens INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT studio_jobs_status_check CHECK (status IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED')),
    CONSTRAINT studio_jobs_operation_unique UNIQUE (tenant_id, operation_key)
);

CREATE TABLE IF NOT EXISTS studio.artifacts (
    artifact_id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    tenant_id TEXT NOT NULL REFERENCES public.tenants(tenant_id) ON DELETE CASCADE,
    collection_id TEXT NOT NULL REFERENCES studio.collections(collection_id) ON DELETE CASCADE,
    owner_user_id TEXT NOT NULL,
    template_id TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'FRESH',
    current_version INTEGER NOT NULL DEFAULT 1,
    cache_fingerprint TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT studio_artifacts_status_check CHECK (status IN ('FRESH', 'STALE', 'ARCHIVED'))
);

CREATE TABLE IF NOT EXISTS studio.artifact_versions (
    version_id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    artifact_id TEXT NOT NULL REFERENCES studio.artifacts(artifact_id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    job_id TEXT REFERENCES studio.studio_jobs(job_id) ON DELETE SET NULL,
    created_by_user_id TEXT NOT NULL,
    content_json JSONB NOT NULL,
    body_md TEXT NOT NULL DEFAULT '',
    groundedness_score NUMERIC(5, 4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT studio_artifact_versions_unique UNIQUE (artifact_id, version_number)
);

CREATE TABLE IF NOT EXISTS studio.artifact_sources (
    artifact_id TEXT NOT NULL REFERENCES studio.artifacts(artifact_id) ON DELETE CASCADE,
    document_id TEXT NOT NULL REFERENCES public.documents(document_id) ON DELETE CASCADE,
    content_sha256 TEXT,
    linked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (artifact_id, document_id)
);

-- Indexes for SKIP LOCKED worker polling and tenant queries
CREATE INDEX IF NOT EXISTS studio_jobs_pending_idx
    ON studio.studio_jobs (status, created_at ASC)
    WHERE status = 'PENDING';

CREATE INDEX IF NOT EXISTS studio_artifacts_tenant_owner_idx
    ON studio.artifacts (tenant_id, owner_user_id, updated_at DESC);

CREATE INDEX IF NOT EXISTS studio_artifact_sources_document_idx
    ON studio.artifact_sources (document_id);

-- Automatic STALE marking when a referenced document is updated or deleted
CREATE OR REPLACE FUNCTION studio.mark_artifacts_stale_on_document_change()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE studio.artifacts a
    SET status = 'STALE', updated_at = NOW()
    WHERE a.status = 'FRESH'
      AND EXISTS (
          SELECT 1 FROM studio.artifact_sources s
          WHERE s.artifact_id = a.artifact_id
            AND s.document_id = COALESCE(NEW.document_id, OLD.document_id)
      );
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS documents_mark_studio_artifacts_stale ON public.documents;
CREATE TRIGGER documents_mark_studio_artifacts_stale
AFTER UPDATE OF status, metadata, updated_at OR DELETE ON public.documents
FOR EACH ROW
EXECUTE FUNCTION studio.mark_artifacts_stale_on_document_change();

