\set ON_ERROR_STOP on
\set QUIET on
\pset format unaligned
\pset tuples_only on
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '30s';
SET LOCAL lock_timeout = '5s';
\ir tenant_preflight_report.sql
\echo :tenant_report
COMMIT;
