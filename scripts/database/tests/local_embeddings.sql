CREATE EXTENSION IF NOT EXISTS vector;

CREATE TEMP TABLE documents (
    document_id text PRIMARY KEY,
    status text NOT NULL
);
CREATE TEMP TABLE document_embeddings (
    document_id text NOT NULL REFERENCES documents,
    embedding vector(1536) NOT NULL,
    embedding_model text NOT NULL DEFAULT 'legacy'
);

INSERT INTO documents VALUES ('fixture', 'PROCESSED'), ('pending', 'PENDING');
INSERT INTO document_embeddings (document_id, embedding)
VALUES ('fixture', array_fill(1.0::real, ARRAY[1536])::vector);

CREATE INDEX fixture_cosine_idx ON document_embeddings
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 1);

\i /tmp/blandskron-local-embeddings.sql

DO $$
BEGIN
    IF (SELECT status FROM documents WHERE document_id = 'fixture') <> 'REINDEX_REQUIRED'
       OR (SELECT status FROM documents WHERE document_id = 'pending') <> 'PENDING'
       OR EXISTS (SELECT 1 FROM document_embeddings) THEN
        RAISE EXCEPTION 'La migración no dejó los documentos listos para reindexar';
    END IF;
END
$$;

INSERT INTO document_embeddings (document_id, embedding)
VALUES ('fixture', array_fill(1.0::real, ARRAY[384])::vector);

\i /tmp/blandskron-local-embeddings.sql

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM document_embeddings
        WHERE document_id = 'fixture'
          AND vector_dims(embedding) = 384
          AND embedding_model = 'intfloat/multilingual-e5-small'
    ) THEN
        RAISE EXCEPTION 'La segunda ejecución alteró el índice nuevo';
    END IF;
END
$$;
