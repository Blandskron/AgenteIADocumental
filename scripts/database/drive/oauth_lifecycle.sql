-- Additive: existing ciphertext and ownership are retained; legacy grants need review/reconnect.
ALTER TABLE public.google_drive_connections
  ADD COLUMN IF NOT EXISTS version bigint NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS grant_status text NOT NULL DEFAULT 'LEGACY',
  ADD COLUMN IF NOT EXISTS provider_account_id text,
  ADD COLUMN IF NOT EXISTS oauth_client_id text,
  ADD COLUMN IF NOT EXISTS lease_token text,
  ADD COLUMN IF NOT EXISTS lease_until timestamptz,
  ADD COLUMN IF NOT EXISTS lease_kind text;
DO $$
DECLARE spec record; actual text;
BEGIN
  FOR spec IN SELECT * FROM (VALUES ('version','int8'),('grant_status','text'),('provider_account_id','text'),
      ('oauth_client_id','text'),('lease_token','text'),('lease_until','timestamptz'),('lease_kind','text')) x(name,kind) LOOP
    SELECT t.typname INTO actual FROM pg_attribute a JOIN pg_type t ON t.oid=a.atttypid
      WHERE a.attrelid='public.google_drive_connections'::regclass AND a.attname=spec.name AND NOT a.attisdropped;
    IF actual IS DISTINCT FROM spec.kind THEN RAISE EXCEPTION 'Incompatible Drive lifecycle schema'; END IF;
  END LOOP;
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='drive_connection_lifecycle_check'
    AND conrelid='public.google_drive_connections'::regclass) THEN
    ALTER TABLE public.google_drive_connections ADD CONSTRAINT drive_connection_lifecycle_check CHECK(
      version>0 AND grant_status IN ('LEGACY','ACTIVE','DISCONNECTED','REAUTH_REQUIRED','REVOKE_PENDING')
      AND ((lease_token IS NULL AND lease_until IS NULL AND lease_kind IS NULL)
           OR (lease_token IS NOT NULL AND lease_until IS NOT NULL AND lease_kind IS NOT NULL AND lease_kind IN ('CONNECT','REFRESH','REVOKE')))
      AND (grant_status<>'ACTIVE' OR (provider_account_id IS NOT NULL AND oauth_client_id IS NOT NULL AND length(access_token_encrypted)>0)));
  END IF;
END $$;
CREATE TABLE IF NOT EXISTS public.google_drive_oauth_attempts(
  state_hash text PRIMARY KEY CHECK(state_hash ~ '^[0-9a-f]{64}$'),
  owner_user_id text NOT NULL,
  identity_binding text NOT NULL CHECK(identity_binding ~ '^[0-9a-f]{64}$'),
  configuration_hash text NOT NULL CHECK(configuration_hash ~ '^[0-9a-f]{64}$'),
  code_challenge text NOT NULL CHECK(code_challenge ~ '^[A-Za-z0-9_-]{43}$'),
  connection_version bigint NOT NULL CHECK(connection_version>0),
  expires_at timestamptz NOT NULL,
  consumed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS drive_oauth_owner_expiry ON public.google_drive_oauth_attempts(owner_user_id,expires_at);
CREATE INDEX IF NOT EXISTS drive_oauth_expiry ON public.google_drive_oauth_attempts(expires_at);
