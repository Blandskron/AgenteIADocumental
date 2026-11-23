-- Document versioning, cross-cutting tags, and shared folders by area/company (EVO-014).
-- Strictly additive & idempotent; never alters or drops existing columns/data.

CREATE TABLE IF NOT EXISTS public.document_versions (
    version_id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    document_id TEXT NOT NULL REFERENCES public.documents(document_id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL CHECK (version_number >= 1),
    storage_path TEXT NOT NULL,
    content_sha256 TEXT,
    size_bytes BIGINT NOT NULL DEFAULT 0 CHECK (size_bytes >= 0),
    change_summary TEXT NOT NULL DEFAULT '',
    created_by_user_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT document_versions_doc_num_unique UNIQUE (document_id, version_number)
);

CREATE TABLE IF NOT EXISTS public.tags (
    tag_id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    tenant_id TEXT NOT NULL REFERENCES public.tenants(tenant_id) ON DELETE CASCADE,
    name TEXT NOT NULL CHECK (char_length(trim(name)) BETWEEN 1 AND 64),
    color TEXT NOT NULL DEFAULT 'slate' CHECK (color ~ '^[a-z0-9_-]{2,24}$'),
    created_by_user_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS tags_tenant_lower_name_uidx
    ON public.tags (tenant_id, lower(trim(name)));

CREATE TABLE IF NOT EXISTS public.document_tags (
    document_id TEXT NOT NULL REFERENCES public.documents(document_id) ON DELETE CASCADE,
    tag_id TEXT NOT NULL REFERENCES public.tags(tag_id) ON DELETE CASCADE,
    tagged_by_user_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (document_id, tag_id)
);

CREATE INDEX IF NOT EXISTS document_versions_document_idx
    ON public.document_versions (document_id, version_number DESC);

CREATE INDEX IF NOT EXISTS document_tags_tag_idx
    ON public.document_tags (tag_id, document_id);

-- Shared folders by area or company (additive columns on document_folders)
ALTER TABLE public.document_folders
    ADD COLUMN IF NOT EXISTS visibility TEXT NOT NULL DEFAULT 'private',
    ADD COLUMN IF NOT EXISTS area_id TEXT REFERENCES public.tenant_areas(area_id) ON DELETE SET NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'document_folders_visibility_check'
    ) THEN
        ALTER TABLE public.document_folders
            ADD CONSTRAINT document_folders_visibility_check
            CHECK (visibility IN ('private', 'area', 'company'));
    END IF;
END
$$;
