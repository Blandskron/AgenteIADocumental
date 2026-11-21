-- Verificación SQL de índices HNSW, Full-Text Search (content_tsv GIN) y trigram en filename (R2-02).
\set ON_ERROR_STOP on

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname = 'public'
          AND tablename = 'document_embeddings'
          AND indexname = 'document_embeddings_embedding_cosine_idx'
          AND indexdef ILIKE '%USING hnsw%'
    ) THEN
        RAISE EXCEPTION 'document_embeddings_embedding_cosine_idx must use HNSW';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname = 'public'
          AND tablename = 'document_embeddings'
          AND indexname = 'document_embeddings_content_tsv_gin_idx'
          AND indexdef ILIKE '%USING gin%'
    ) THEN
        RAISE EXCEPTION 'document_embeddings_content_tsv_gin_idx GIN index is missing';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname = 'public'
          AND tablename = 'documents'
          AND indexname = 'documents_filename_trgm_idx'
          AND indexdef ILIKE '%gin_trgm_ops%'
    ) THEN
        RAISE EXCEPTION 'documents_filename_trgm_idx trigram index is missing';
    END IF;
END
$$;

INSERT INTO public.documents (document_id, filename, storage_path, mime_type)
VALUES ('r202-synthetic-doc', 'acta_comite_2026_014.md', 'r202.md', 'text/markdown');

INSERT INTO public.document_embeddings (document_id, chunk_index, chunk_content, embedding)
VALUES (
    'r202-synthetic-doc',
    0,
    'El plazo maximo aprobado en ACTA-2026-014 para migrar a HNSW es de 45 dias.',
    ('[' || array_to_string(ARRAY(SELECT CASE WHEN i = 1 THEN '1' ELSE '0' END FROM generate_series(1, 384) i), ',') || ']')::vector(384)
);

DO $$
DECLARE
    fts_hits integer;
BEGIN
    SELECT count(*) INTO fts_hits
    FROM public.document_embeddings
    WHERE document_id = 'r202-synthetic-doc'
      AND content_tsv @@ websearch_to_tsquery('spanish', 'plazo HNSW');
    IF fts_hits <> 1 THEN
        RAISE EXCEPTION 'Generated content_tsv did not match synthetic FTS query (hits=%)', fts_hits;
    END IF;
END
$$;

ROLLBACK;
