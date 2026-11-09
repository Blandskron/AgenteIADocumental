-- Additive operation journal; deploy with all old import writers stopped.
ALTER TABLE public.google_drive_imports
  ADD COLUMN IF NOT EXISTS operation_id text,
  ADD COLUMN IF NOT EXISTS request_hash text,
  ADD COLUMN IF NOT EXISTS tenant_id text,
  ADD COLUMN IF NOT EXISTS connection_version bigint,
  ADD COLUMN IF NOT EXISTS version bigint NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS lease_token text,
  ADD COLUMN IF NOT EXISTS lease_until timestamptz;
CREATE UNIQUE INDEX IF NOT EXISTS drive_import_operation_unique
  ON public.google_drive_imports(owner_user_id,operation_id) WHERE operation_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS drive_import_lease_expiry ON public.google_drive_imports(lease_until) WHERE lease_token IS NOT NULL;
-- Legacy interrupted operations cannot safely be treated as failed uploads.
UPDATE public.google_drive_import_files f SET status='REVIEW_REQUIRED',error_message='Legacy interrupted import requires review.'
 FROM public.google_drive_imports i WHERE i.import_id=f.import_id AND i.operation_id IS NULL AND f.status IN ('RUNNING','UPLOADING','DOWNLOADING','PENDING');
UPDATE public.google_drive_imports SET status='REVIEW_REQUIRED',error_message='Legacy interrupted import requires review.'
 WHERE operation_id IS NULL AND status IN ('RUNNING','PENDING');
DO $$
DECLARE spec record; actual text;
BEGIN
  FOR spec IN SELECT * FROM (VALUES ('operation_id','text'),('request_hash','text'),('tenant_id','text'),
    ('connection_version','int8'),('version','int8'),('lease_token','text'),('lease_until','timestamptz')) x(name,kind) LOOP
    SELECT t.typname INTO actual FROM pg_attribute a JOIN pg_type t ON t.oid=a.atttypid
      WHERE a.attrelid='public.google_drive_imports'::regclass AND a.attname=spec.name AND NOT a.attisdropped;
    IF actual IS DISTINCT FROM spec.kind THEN RAISE EXCEPTION 'Incompatible Drive import schema'; END IF;
  END LOOP;
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='drive_import_lease_check' AND conrelid='public.google_drive_imports'::regclass) THEN
    ALTER TABLE public.google_drive_imports ADD CONSTRAINT drive_import_lease_check CHECK(
      version>0 AND ((lease_token IS NULL AND lease_until IS NULL) OR (lease_token IS NOT NULL AND lease_until IS NOT NULL))
      AND (operation_id IS NULL OR (request_hash IS NOT NULL AND request_hash ~ '^[0-9a-f]{64}$' AND connection_version IS NOT NULL AND connection_version>0)));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS drive_import_file_parent_order ON public.google_drive_import_files(import_id,created_at,import_file_id);
CREATE INDEX IF NOT EXISTS drive_import_file_source ON public.google_drive_import_files(google_file_id,import_id);

CREATE INDEX IF NOT EXISTS drive_import_owner_page ON public.google_drive_imports(owner_user_id,created_at DESC,import_id DESC);
