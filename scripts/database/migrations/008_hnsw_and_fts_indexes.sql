\set ON_ERROR_STOP on
-- Idempotent migration: replace ivfflat with HNSW, add generated content_tsv + GIN, and filename trigram index (R2-02).

BEGIN;

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE public.document_embeddings
    ADD COLUMN IF NOT EXISTS content_tsv tsvector
        GENERATED ALWAYS AS (to_tsvector('spanish', COALESCE(chunk_content, ''))) STORED;

CREATE INDEX IF NOT EXISTS document_embeddings_content_tsv_gin_idx
    ON public.document_embeddings USING GIN (content_tsv);

CREATE INDEX IF NOT EXISTS documents_filename_trgm_idx
    ON public.documents USING GIN (filename gin_trgm_ops);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname = 'public'
          AND tablename = 'document_embeddings'
          AND indexname = 'document_embeddings_embedding_cosine_idx'
          AND indexdef NOT ILIKE '%USING hnsw%'
    ) THEN
        DROP INDEX public.document_embeddings_embedding_cosine_idx;
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS document_embeddings_embedding_cosine_idx
    ON public.document_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

COMMIT;
