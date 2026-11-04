BEGIN;

LOCK TABLE documents, document_embeddings IN ACCESS EXCLUSIVE MODE;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_attribute
        WHERE attrelid = 'document_embeddings'::regclass
          AND attname = 'embedding'
          AND format_type(atttypid, atttypmod) = 'vector(1536)'
    ) THEN
        UPDATE documents
        SET status = 'REINDEX_REQUIRED'
        WHERE status IN ('PROCESSED', 'PROCESSING')
           OR EXISTS (
               SELECT 1 FROM document_embeddings
               WHERE document_embeddings.document_id = documents.document_id
           );

        TRUNCATE document_embeddings;
        ALTER TABLE document_embeddings
            ALTER COLUMN embedding TYPE vector(384) USING embedding::vector(384),
            ALTER COLUMN embedding_model SET DEFAULT 'intfloat/multilingual-e5-small';
    END IF;
END
$$;

COMMIT;
