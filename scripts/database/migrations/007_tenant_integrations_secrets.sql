\set ON_ERROR_STOP on
-- Additive, idempotent migration for AI/provider integration secrets on tenant_integrations (R1-01).
-- Reversible via:
--   ALTER TABLE public.tenant_integrations
--       DROP COLUMN IF EXISTS secrets_encrypted,
--       DROP COLUMN IF EXISTS updated_by_user_id;

BEGIN;

ALTER TABLE public.tenant_integrations
    ADD COLUMN IF NOT EXISTS secrets_encrypted TEXT,
    ADD COLUMN IF NOT EXISTS updated_by_user_id TEXT;

COMMIT;

