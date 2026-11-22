-- Verificación SQL de esquema studio.*: colecciones, cola SKIP LOCKED, artefactos versionados y STALE automático (R4-01).
\set ON_ERROR_STOP on

BEGIN;

INSERT INTO public.tenants (tenant_id, name) VALUES ('studio-t1', 'Studio Synthetic Tenant');
INSERT INTO public.documents (document_id, tenant_id, owner_user_id, filename, storage_path, mime_type, status)
VALUES ('studio-doc-1', 'studio-t1', '42', 'acta.md', 'acta.md', 'text/markdown', 'PROCESSED');

INSERT INTO studio.collections (collection_id, tenant_id, owner_user_id, title, visibility)
VALUES ('col-1', 'studio-t1', '42', 'Coleccion Sintetica', 'private');

INSERT INTO studio.collection_documents (collection_id, document_id, content_sha256, added_by_user_id)
VALUES ('col-1', 'studio-doc-1', 'sha-v1', '42');

INSERT INTO studio.studio_jobs (job_id, tenant_id, collection_id, created_by_user_id, operation_key, template_id)
VALUES ('job-1', 'studio-t1', 'col-1', '42', 'op-unique-1', 'summary.executive');

-- Idempotency check on (tenant_id, operation_key)
DO $$
BEGIN
    BEGIN
        INSERT INTO studio.studio_jobs (tenant_id, collection_id, created_by_user_id, operation_key, template_id)
        VALUES ('studio-t1', 'col-1', '42', 'op-unique-1', 'summary.executive');
        RAISE EXCEPTION 'Duplicate studio job operation_key was allowed';
    EXCEPTION WHEN unique_violation THEN
        NULL;
    END;
END
$$;

INSERT INTO studio.artifacts (artifact_id, tenant_id, collection_id, owner_user_id, template_id, title, status)
VALUES ('art-1', 'studio-t1', 'col-1', '42', 'summary.executive', 'Resumen Ejecutivo', 'FRESH');

INSERT INTO studio.artifact_versions (artifact_id, version_number, job_id, created_by_user_id, content_json, body_md, groundedness_score)
VALUES ('art-1', 1, 'job-1', '42', '{"kind":"summary"}'::jsonb, '# Resumen', 1.0000);

INSERT INTO studio.artifact_sources (artifact_id, document_id, content_sha256)
VALUES ('art-1', 'studio-doc-1', 'sha-v1');

-- Updating referenced document must flip artifact status from FRESH -> STALE automatically.
UPDATE public.documents SET status = 'REINDEX_REQUIRED' WHERE document_id = 'studio-doc-1';

DO $$
DECLARE
    current_status TEXT;
BEGIN
    SELECT status INTO current_status FROM studio.artifacts WHERE artifact_id = 'art-1';
    IF current_status <> 'STALE' THEN
        RAISE EXCEPTION 'Expected artifact status STALE after document update, got %', current_status;
    END IF;
END
$$;

-- Deleting tenant cascades cleanly across studio.* tables.
DELETE FROM public.tenants WHERE tenant_id = 'studio-t1';

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM studio.artifacts WHERE artifact_id = 'art-1')
       OR EXISTS (SELECT 1 FROM studio.studio_jobs WHERE job_id = 'job-1') THEN
        RAISE EXCEPTION 'ON DELETE CASCADE failed for studio schema';
    END IF;
END
$$;

ROLLBACK;

