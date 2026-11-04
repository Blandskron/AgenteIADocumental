CREATE TABLE IF NOT EXISTS notifications (
    notification_id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    tenant_id TEXT REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    recipient_user_id TEXT NOT NULL,
    actor_user_id TEXT,
    document_id TEXT REFERENCES documents(document_id) ON DELETE CASCADE,
    assignment_id TEXT REFERENCES document_assignments(assignment_id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'UNREAD',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    read_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT notifications_status_check CHECK (status IN ('UNREAD', 'READ', 'ARCHIVED'))
);

CREATE TABLE IF NOT EXISTS audit_logs (
    audit_id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    tenant_id TEXT REFERENCES tenants(tenant_id) ON DELETE SET NULL,
    actor_user_id TEXT,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT,
    target_user_id TEXT,
    ip_address TEXT,
    user_agent TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tenant_integrations (
    integration_id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'DISABLED',
    enabled_for_roles JSONB NOT NULL DEFAULT '[]'::jsonb,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT tenant_integrations_status_check CHECK (status IN ('ENABLED', 'DISABLED')),
    CONSTRAINT tenant_integrations_provider_unique UNIQUE (tenant_id, provider)
);
