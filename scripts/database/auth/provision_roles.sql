\getenv runtime_password AUTH_DB_RUNTIME_PASSWORD
\getenv migrate_password AUTH_DB_MIGRATE_PASSWORD

BEGIN;

-- Role provisioners share the public schema ACL and must update it serially.
SELECT pg_advisory_xact_lock(hashtextextended('blandskron.database.role_provisioning', 0));

SELECT 'CREATE ROLE auth_runtime' WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'auth_runtime') \gexec
SELECT 'CREATE ROLE auth_migrate' WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'auth_migrate') \gexec

ALTER ROLE auth_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS
    PASSWORD :'runtime_password';
ALTER ROLE auth_migrate LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS
    PASSWORD :'migrate_password';

GRANT USAGE ON SCHEMA public TO auth_runtime;
GRANT USAGE, CREATE ON SCHEMA public TO auth_migrate;
REVOKE CREATE ON SCHEMA public FROM auth_runtime;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_auth_members membership
        JOIN pg_roles member ON member.oid = membership.member
        WHERE member.rolname IN ('auth_runtime', 'auth_migrate')
    ) THEN
        RAISE EXCEPTION 'Auth database roles must not be members of other roles.';
    END IF;
    IF has_schema_privilege('auth_runtime', 'public', 'CREATE') THEN
        RAISE EXCEPTION 'auth_runtime inherits CREATE on public. Review PUBLIC grants and role membership.';
    END IF;
END
$$;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
    public.tenants, public.tenant_areas, public.tenant_memberships, public.tenant_groups,
    public.tenant_group_permissions, public.tenant_user_groups
TO auth_runtime;

-- Transfer only Django-owned tables from an existing installation.
SELECT format('ALTER TABLE public.%I OWNER TO auth_migrate', tablename)
FROM pg_tables
WHERE schemaname = 'public' AND tableowner <> 'auth_migrate' AND tablename IN (
    'auth_group', 'auth_group_permissions', 'auth_permission', 'auth_user',
    'auth_user_groups', 'auth_user_user_permissions', 'django_admin_log',
    'django_content_type', 'django_migrations', 'django_session',
    'token_blacklist_blacklistedtoken', 'token_blacklist_outstandingtoken', 'users_loginattemptbudget'
)
\gexec

COMMIT;
