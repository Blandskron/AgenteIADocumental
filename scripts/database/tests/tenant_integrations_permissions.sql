-- Verificación SQL sintética de tenant_integrations: columnas aditivas, unicidad por tenant,
-- borrado en cascada, permisos de auth_runtime y lectura mínima de rag_chat_runtime (R1-01).
\set ON_ERROR_STOP on

BEGIN;

-- 1. Verificar existencia y tipo de las columnas aditivas.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'tenant_integrations'
          AND column_name = 'secrets_encrypted' AND data_type = 'text'
    ) OR NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'tenant_integrations'
          AND column_name = 'updated_by_user_id' AND data_type = 'text'
    ) THEN
        RAISE EXCEPTION 'tenant_integrations missing additive columns secrets_encrypted / updated_by_user_id';
    END IF;
END
$$;

-- 2. Preparar dos tenants sintéticos.
INSERT INTO public.tenants (tenant_id, name)
VALUES ('r1-tenant-a', 'Synthetic Tenant A'),
       ('r1-tenant-b', 'Synthetic Tenant B');

-- 3. Verificar que auth_runtime puede crear, leer y actualizar filas de tenant_integrations.
SET LOCAL ROLE auth_runtime;

INSERT INTO public.tenant_integrations (
    tenant_id, provider, status, config, secrets_encrypted, updated_by_user_id
) VALUES (
    'r1-tenant-a',
    'groq',
    'ENABLED',
    '{"model": "llama-3.3-70b-versatile"}'::jsonb,
    'secrets1.k1.synthetic-ciphertext-a',
    '101'
);

INSERT INTO public.tenant_integrations (
    tenant_id, provider, status, config, secrets_encrypted, updated_by_user_id
) VALUES (
    'r1-tenant-b',
    'groq',
    'DISABLED',
    '{"model": "llama-3.3-70b-versatile"}'::jsonb,
    'secrets1.k1.synthetic-ciphertext-b',
    '202'
);

-- Verificar restricción única (tenant_id, provider).
DO $$
BEGIN
    BEGIN
        INSERT INTO public.tenant_integrations (tenant_id, provider, status)
        VALUES ('r1-tenant-a', 'groq', 'DISABLED');
        RAISE EXCEPTION 'Duplicate (tenant_id, provider) was unexpectedly allowed';
    EXCEPTION WHEN unique_violation THEN
        NULL;
    END;
END
$$;

-- 4. Verificar que rag_chat_runtime solo puede leer columnas permitidas y nunca escribir ni leer columnas administrativas.
RESET ROLE;
SET LOCAL ROLE rag_chat_runtime;

DO $$
DECLARE
    row_count integer;
BEGIN
    SELECT count(*) INTO row_count
    FROM public.tenant_integrations
    WHERE tenant_id = 'r1-tenant-a' AND provider = 'groq' AND status = 'ENABLED'
      AND secrets_encrypted = 'secrets1.k1.synthetic-ciphertext-a';

    IF row_count <> 1 THEN
        RAISE EXCEPTION 'rag_chat_runtime could not read active tenant integration row';
    END IF;

    BEGIN
        UPDATE public.tenant_integrations SET status = 'DISABLED' WHERE tenant_id = 'r1-tenant-a';
        RAISE EXCEPTION 'rag_chat_runtime was able to UPDATE tenant_integrations';
    EXCEPTION WHEN insufficient_privilege THEN
        NULL;
    END;

    BEGIN
        DELETE FROM public.tenant_integrations WHERE tenant_id = 'r1-tenant-a';
        RAISE EXCEPTION 'rag_chat_runtime was able to DELETE tenant_integrations';
    EXCEPTION WHEN insufficient_privilege THEN
        NULL;
    END;

    BEGIN
        PERFORM updated_by_user_id FROM public.tenant_integrations LIMIT 1;
        RAISE EXCEPTION 'rag_chat_runtime was able to read updated_by_user_id';
    EXCEPTION WHEN insufficient_privilege THEN
        NULL;
    END;
END
$$;

-- 5. Verificar borrado en cascada al eliminar tenant.
RESET ROLE;
DELETE FROM public.tenants WHERE tenant_id = 'r1-tenant-a';

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM public.tenant_integrations WHERE tenant_id = 'r1-tenant-a') THEN
        RAISE EXCEPTION 'ON DELETE CASCADE failed for tenant_integrations';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM public.tenant_integrations WHERE tenant_id = 'r1-tenant-b') THEN
        RAISE EXCEPTION 'Deleting tenant A affected tenant B integration';
    END IF;
END
$$;

ROLLBACK;
