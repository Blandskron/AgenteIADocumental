BEGIN;

SET LOCAL ROLE auth_runtime;

DO $$
BEGIN
    IF NOT has_table_privilege(current_user, 'public.auth_user', 'SELECT')
       OR NOT has_table_privilege(current_user, 'public.users_loginattemptbudget', 'INSERT')
       OR NOT has_table_privilege(current_user, 'public.tenant_memberships', 'UPDATE') THEN
        RAISE EXCEPTION 'auth_runtime lacks required application permissions';
    END IF;

    IF has_table_privilege(current_user, 'public.documents', 'SELECT')
       OR has_table_privilege(current_user, 'public.django_migrations', 'UPDATE')
       OR has_schema_privilege(current_user, 'public', 'CREATE') THEN
        RAISE EXCEPTION 'auth_runtime has permissions beyond its application scope';
    END IF;

    BEGIN
        CREATE TABLE public.auth_runtime_permission_probe (id integer);
        RAISE EXCEPTION 'auth_runtime was able to create a permanent table';
    EXCEPTION WHEN insufficient_privilege THEN
        NULL;
    END;
END
$$;

SET LOCAL ROLE auth_migrate;

CREATE TABLE public.auth_migration_permission_probe (id integer);

DO $$
BEGIN
    IF NOT has_table_privilege(current_user, 'public.django_migrations', 'UPDATE')
       OR has_table_privilege(current_user, 'public.documents', 'SELECT') THEN
        RAISE EXCEPTION 'auth_migrate has incorrect permissions';
    END IF;
END
$$;

ROLLBACK;
