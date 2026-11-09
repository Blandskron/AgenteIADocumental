-- Blandskron Documental database bootstrap.
-- Keep this file as the only orchestration point for schema setup.

BEGIN;

\ir extensions/001_extensions.sql
\ir schemas/003_tenants.sql
\ir schemas/001_documents.sql
\ir schemas/002_conversations.sql
\ir schemas/008_profiles.sql
\ir profile/audit_profiles.sql
\ir profile/versions.sql
\ir profile/avatars.sql
\ir schemas/009_exports.sql
\ir export/pdf_storage.sql
\ir schemas/010_google_drive_imports.sql
\ir drive/oauth_lifecycle.sql
\ir drive/import_lifecycle.sql
\ir schemas/011_notifications_audit.sql
\ir schemas/012_document_deletions.sql
\ir constraints/001_document_constraints.sql
\ir migrations/002_library_integrity.sql
\ir indexes/001_indexes.sql
\ir functions/001_functions.sql
\ir triggers/001_updated_at_triggers.sql
\ir seeds/001_reference_data.sql

COMMIT;

-- After loading many embeddings, run:
-- ANALYZE document_embeddings;
