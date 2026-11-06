\getenv runtime_password LIBRARY_DB_PASSWORD

BEGIN;
SELECT pg_advisory_xact_lock(hashtextextended('blandskron.database.role_provisioning', 0));
SELECT 'CREATE ROLE document_library_runtime'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'document_library_runtime') \gexec
SELECT 'CREATE ROLE document_library_reference_owner'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'document_library_reference_owner') \gexec

ALTER ROLE document_library_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS
    PASSWORD :'runtime_password';
ALTER ROLE document_library_reference_owner NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
\ir permissions.sql
\ir verify_role.sql
COMMIT;
