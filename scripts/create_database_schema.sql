-- Compatibility entrypoint.
-- The database schema is now split by concern under scripts/database/.
-- Use this file when older commands still reference scripts/create_database_schema.sql.

\ir database/run_all.sql
