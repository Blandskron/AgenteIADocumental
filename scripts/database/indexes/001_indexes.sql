CREATE INDEX IF NOT EXISTS documents_status_created_at_idx
    ON documents (status, created_at);

CREATE INDEX IF NOT EXISTS documents_tenant_status_created_at_idx
    ON documents (tenant_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS documents_tenant_owner_idx
    ON documents (tenant_id, owner_user_id);

CREATE INDEX IF NOT EXISTS documents_tenant_area_idx
    ON documents (tenant_id, owner_area_id);

CREATE INDEX IF NOT EXISTS documents_metadata_gin_idx
    ON documents USING GIN (metadata);

CREATE INDEX IF NOT EXISTS document_embeddings_document_id_idx
    ON document_embeddings (document_id);

CREATE INDEX IF NOT EXISTS document_embeddings_metadata_gin_idx
    ON document_embeddings USING GIN (metadata);

CREATE INDEX IF NOT EXISTS document_embeddings_embedding_cosine_idx
    ON document_embeddings
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE UNIQUE INDEX IF NOT EXISTS tenants_tax_id_unique
    ON tenants (tax_id)
    WHERE tax_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS tenant_areas_tenant_parent_name_unique
    ON tenant_areas (tenant_id, parent_area_id, name)
    WHERE parent_area_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS tenant_areas_tenant_root_name_unique
    ON tenant_areas (tenant_id, name)
    WHERE parent_area_id IS NULL;

CREATE INDEX IF NOT EXISTS tenant_memberships_user_status_idx
    ON tenant_memberships (user_id, status);

CREATE INDEX IF NOT EXISTS tenant_memberships_tenant_role_idx
    ON tenant_memberships (tenant_id, role, status);

CREATE INDEX IF NOT EXISTS tenant_groups_tenant_idx
    ON tenant_groups (tenant_id, name);

CREATE INDEX IF NOT EXISTS tenant_user_groups_user_idx
    ON tenant_user_groups (user_id, tenant_id);

CREATE INDEX IF NOT EXISTS chat_messages_owner_session_created_at_idx
    ON chat_messages (owner_user_id, session_id, created_at DESC);

CREATE INDEX IF NOT EXISTS document_folders_owner_parent_idx
    ON document_folders (owner_user_id, parent_folder_id);

CREATE UNIQUE INDEX IF NOT EXISTS document_folders_owner_root_name_unique
    ON document_folders (owner_user_id, name)
    WHERE parent_folder_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS document_folders_owner_child_name_unique
    ON document_folders (owner_user_id, parent_folder_id, name)
    WHERE parent_folder_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS document_folder_items_owner_idx
    ON document_folder_items (owner_user_id, added_at DESC);

CREATE INDEX IF NOT EXISTS document_favorites_owner_created_idx
    ON document_favorites (owner_user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS document_assignments_tenant_assigned_status_idx
    ON document_assignments (tenant_id, assigned_to_user_id, status);

CREATE INDEX IF NOT EXISTS document_assignments_document_idx
    ON document_assignments (document_id);

CREATE INDEX IF NOT EXISTS document_assignments_assigned_by_idx
    ON document_assignments (assigned_by_user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS document_assignment_events_assignment_created_idx
    ON document_assignment_events (assignment_id, created_at ASC);

CREATE INDEX IF NOT EXISTS notifications_recipient_status_created_idx
    ON notifications (recipient_user_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS notifications_tenant_created_idx
    ON notifications (tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS audit_logs_tenant_created_idx
    ON audit_logs (tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS audit_logs_resource_idx
    ON audit_logs (resource_type, resource_id, created_at DESC);

CREATE INDEX IF NOT EXISTS tenant_integrations_tenant_provider_idx
    ON tenant_integrations (tenant_id, provider);

CREATE INDEX IF NOT EXISTS transfer_events_owner_created_idx
    ON transfer_events (owner_user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS conversations_owner_updated_idx
    ON conversations (owner_user_id, updated_at DESC);

CREATE INDEX IF NOT EXISTS conversation_messages_conversation_created_idx
    ON conversation_messages (conversation_id, created_at ASC);

CREATE INDEX IF NOT EXISTS conversation_documents_owner_idx
    ON conversation_documents (owner_user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS document_exports_owner_created_idx
    ON document_exports (owner_user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS document_exports_source_idx
    ON document_exports (source_type, source_id);

CREATE INDEX IF NOT EXISTS document_exports_metadata_gin_idx
    ON document_exports USING GIN (metadata);

CREATE INDEX IF NOT EXISTS google_drive_connections_owner_idx
    ON google_drive_connections (owner_user_id);

CREATE INDEX IF NOT EXISTS google_drive_imports_owner_created_idx
    ON google_drive_imports (owner_user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS google_drive_imports_status_idx
    ON google_drive_imports (status, created_at DESC);

CREATE INDEX IF NOT EXISTS google_drive_import_files_import_idx
    ON google_drive_import_files (import_id, created_at ASC);

CREATE INDEX IF NOT EXISTS google_drive_import_files_document_idx
    ON google_drive_import_files (document_id);

CREATE INDEX IF NOT EXISTS google_drive_import_files_metadata_gin_idx
    ON google_drive_import_files USING GIN (metadata);
