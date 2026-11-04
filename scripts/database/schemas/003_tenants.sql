CREATE TABLE IF NOT EXISTS tenants (
    tenant_id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    name TEXT NOT NULL,
    tax_id TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_by_user_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT tenants_status_check CHECK (status IN ('ACTIVE', 'SUSPENDED', 'DISABLED'))
);

CREATE TABLE IF NOT EXISTS tenant_areas (
    area_id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    parent_area_id TEXT REFERENCES tenant_areas(area_id) ON DELETE SET NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tenant_memberships (
    membership_id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    area_id TEXT REFERENCES tenant_areas(area_id) ON DELETE SET NULL,
    role TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_by_user_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT tenant_memberships_role_check CHECK (role IN ('TENANT_ADMIN', 'LEADER', 'USER')),
    CONSTRAINT tenant_memberships_status_check CHECK (status IN ('ACTIVE', 'PENDING', 'DISABLED')),
    CONSTRAINT tenant_memberships_user_tenant_unique UNIQUE (tenant_id, user_id)
);

CREATE TABLE IF NOT EXISTS tenant_role_permissions (
    tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    permission_code TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, role, permission_code),
    CONSTRAINT tenant_role_permissions_role_check CHECK (role IN ('TENANT_ADMIN', 'LEADER', 'USER'))
);

CREATE TABLE IF NOT EXISTS tenant_groups (
    group_id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    is_system BOOLEAN NOT NULL DEFAULT FALSE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT tenant_groups_tenant_name_unique UNIQUE (tenant_id, name)
);

CREATE TABLE IF NOT EXISTS tenant_group_permissions (
    permission_id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    group_id TEXT NOT NULL REFERENCES tenant_groups(group_id) ON DELETE CASCADE,
    permission_code TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT tenant_group_permissions_group_code_unique UNIQUE (group_id, permission_code)
);

CREATE TABLE IF NOT EXISTS tenant_user_groups (
    user_group_id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    group_id TEXT NOT NULL REFERENCES tenant_groups(group_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT tenant_user_groups_tenant_user_group_unique UNIQUE (tenant_id, user_id, group_id)
);

ALTER TABLE tenant_group_permissions
    ADD COLUMN IF NOT EXISTS permission_id TEXT DEFAULT gen_random_uuid()::text;

UPDATE tenant_group_permissions
SET permission_id = gen_random_uuid()::text
WHERE permission_id IS NULL;

ALTER TABLE tenant_group_permissions
    ALTER COLUMN permission_id SET NOT NULL;

ALTER TABLE tenant_group_permissions
    DROP CONSTRAINT IF EXISTS tenant_group_permissions_pkey;

ALTER TABLE tenant_group_permissions
    ADD CONSTRAINT tenant_group_permissions_pkey PRIMARY KEY (permission_id);

ALTER TABLE tenant_group_permissions
    DROP CONSTRAINT IF EXISTS tenant_group_permissions_group_code_unique;

ALTER TABLE tenant_group_permissions
    ADD CONSTRAINT tenant_group_permissions_group_code_unique UNIQUE (group_id, permission_code);

ALTER TABLE tenant_user_groups
    ADD COLUMN IF NOT EXISTS user_group_id TEXT DEFAULT gen_random_uuid()::text;

UPDATE tenant_user_groups
SET user_group_id = gen_random_uuid()::text
WHERE user_group_id IS NULL;

ALTER TABLE tenant_user_groups
    ALTER COLUMN user_group_id SET NOT NULL;

ALTER TABLE tenant_user_groups
    DROP CONSTRAINT IF EXISTS tenant_user_groups_pkey;

ALTER TABLE tenant_user_groups
    ADD CONSTRAINT tenant_user_groups_pkey PRIMARY KEY (user_group_id);

ALTER TABLE tenant_user_groups
    DROP CONSTRAINT IF EXISTS tenant_user_groups_tenant_user_group_unique;

ALTER TABLE tenant_user_groups
    ADD CONSTRAINT tenant_user_groups_tenant_user_group_unique UNIQUE (tenant_id, user_id, group_id);
