\getenv runtime_password PROFILE_DB_PASSWORD
BEGIN;
SELECT pg_advisory_xact_lock(hashtextextended('blandskron.database.role_provisioning', 0));
SELECT 'CREATE ROLE profile_runtime' WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='profile_runtime') \gexec
SELECT 'CREATE ROLE profile_identity_owner' WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='profile_identity_owner') \gexec
ALTER ROLE profile_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD :'runtime_password';
ALTER ROLE profile_identity_owner NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
\ir permissions.sql
\ir verify_role.sql
COMMIT;
