\getenv runtime_password DRIVE_DB_PASSWORD
BEGIN;
SELECT pg_advisory_xact_lock(hashtextextended('blandskron.database.role_provisioning',0));
SELECT 'CREATE ROLE drive_runtime' WHERE NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='drive_runtime') \gexec
SELECT 'CREATE ROLE drive_helper_owner' WHERE NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='drive_helper_owner') \gexec
ALTER ROLE drive_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD :'runtime_password';
ALTER ROLE drive_helper_owner NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
\ir permissions.sql
\ir verify_role.sql
COMMIT;
