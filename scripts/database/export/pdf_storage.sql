-- Additive, repeatable migration: historical rows/files are preserved unchanged.
ALTER TABLE document_exports ADD COLUMN IF NOT EXISTS pdf_data BYTEA;
ALTER TABLE document_exports ADD COLUMN IF NOT EXISTS pdf_sha256 TEXT;
ALTER TABLE document_exports ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;
ALTER TABLE document_exports ADD COLUMN IF NOT EXISTS operation_key TEXT;
ALTER TABLE document_exports ADD COLUMN IF NOT EXISTS request_sha256 TEXT;
DO $$ BEGIN
    IF EXISTS (
        SELECT 1 FROM (VALUES ('pdf_data','bytea'),('pdf_sha256','text'),('expires_at','timestamptz'),
                              ('operation_key','text'),('request_sha256','text')) AS expected(name,type)
        LEFT JOIN pg_attribute a ON a.attrelid='public.document_exports'::regclass AND a.attname=expected.name
        WHERE a.atttypid IS DISTINCT FROM to_regtype(expected.type) OR a.attnotnull
    ) THEN
        RAISE EXCEPTION 'Incompatible export storage columns; explicit repair required.';
    END IF;
END $$;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='document_exports_pdf_integrity' AND conrelid='public.document_exports'::regclass) THEN
        ALTER TABLE document_exports ADD CONSTRAINT document_exports_pdf_integrity CHECK (
            (pdf_data IS NULL AND pdf_sha256 IS NULL)
            OR (pdf_data IS NOT NULL AND pdf_sha256 IS NOT NULL AND
                octet_length(pdf_data) BETWEEN 1 AND 1048576 AND
                file_size_bytes=octet_length(pdf_data) AND
                pdf_sha256=encode(sha256(pdf_data),'hex'))
        );
    END IF;
END $$;
CREATE UNIQUE INDEX IF NOT EXISTS idx_exports_owner_operation ON document_exports(owner_user_id,operation_key) WHERE operation_key IS NOT NULL;
