-- Read-only postflight for the dedicated bd-final-check project, never a personal DB.
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '30s';
SET LOCAL lock_timeout = '5s';
DO $$
BEGIN
    -- The installation now deliberately retains its bootstrapped administrator.
    IF (SELECT count(*) FROM auth_user) <> 1
       OR NOT EXISTS (SELECT FROM auth_user WHERE username='synthetic-release-admin' AND is_superuser AND is_active)
       OR EXISTS (SELECT FROM tenants)
       OR EXISTS (SELECT FROM tenant_memberships)
       OR EXISTS (SELECT FROM documents)
       OR EXISTS (SELECT FROM document_exports)
       OR EXISTS (SELECT FROM pg_database WHERE datname LIKE 'plat_%_release') THEN
        RAISE EXCEPTION 'Synthetic release fixtures remain; inspect the dedicated project before cleanup.';
    END IF;
END $$;
SELECT json_build_object('bootstrap_administrators', 1, 'fixture_users', 0, 'tenants', 0, 'memberships', 0,
                         'documents', 0, 'exports', 0, 'auxiliary_databases', 0) AS cleanup;
ROLLBACK;
