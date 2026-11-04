DROP TRIGGER IF EXISTS documents_set_updated_at ON documents;
CREATE TRIGGER documents_set_updated_at
BEFORE UPDATE ON documents
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS tenants_set_updated_at ON tenants;
CREATE TRIGGER tenants_set_updated_at
BEFORE UPDATE ON tenants
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS tenant_areas_set_updated_at ON tenant_areas;
CREATE TRIGGER tenant_areas_set_updated_at
BEFORE UPDATE ON tenant_areas
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS tenant_memberships_set_updated_at ON tenant_memberships;
CREATE TRIGGER tenant_memberships_set_updated_at
BEFORE UPDATE ON tenant_memberships
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS tenant_groups_set_updated_at ON tenant_groups;
CREATE TRIGGER tenant_groups_set_updated_at
BEFORE UPDATE ON tenant_groups
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS document_folders_set_updated_at ON document_folders;
CREATE TRIGGER document_folders_set_updated_at
BEFORE UPDATE ON document_folders
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS transfer_events_set_updated_at ON transfer_events;
CREATE TRIGGER transfer_events_set_updated_at
BEFORE UPDATE ON transfer_events
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS document_assignments_set_updated_at ON document_assignments;
CREATE TRIGGER document_assignments_set_updated_at
BEFORE UPDATE ON document_assignments
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS notifications_set_updated_at ON notifications;
CREATE TRIGGER notifications_set_updated_at
BEFORE UPDATE ON notifications
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS tenant_integrations_set_updated_at ON tenant_integrations;
CREATE TRIGGER tenant_integrations_set_updated_at
BEFORE UPDATE ON tenant_integrations
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS conversations_set_updated_at ON conversations;
CREATE TRIGGER conversations_set_updated_at
BEFORE UPDATE ON conversations
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS user_profiles_set_updated_at ON user_profiles;
CREATE TRIGGER user_profiles_set_updated_at
BEFORE UPDATE ON user_profiles
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS document_exports_set_updated_at ON document_exports;
CREATE TRIGGER document_exports_set_updated_at
BEFORE UPDATE ON document_exports
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS google_drive_connections_set_updated_at ON google_drive_connections;
CREATE TRIGGER google_drive_connections_set_updated_at
BEFORE UPDATE ON google_drive_connections
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS google_drive_imports_set_updated_at ON google_drive_imports;
CREATE TRIGGER google_drive_imports_set_updated_at
BEFORE UPDATE ON google_drive_imports
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS google_drive_import_files_set_updated_at ON google_drive_import_files;
CREATE TRIGGER google_drive_import_files_set_updated_at
BEFORE UPDATE ON google_drive_import_files
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();
