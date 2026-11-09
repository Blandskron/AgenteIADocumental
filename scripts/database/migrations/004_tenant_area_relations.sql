\set ON_ERROR_STOP on
BEGIN;
SET LOCAL lock_timeout = '5s';
LOCK TABLE public.tenants, public.tenant_areas, public.tenant_groups,
    public.tenant_memberships, public.tenant_user_groups, public.documents
    IN SHARE ROW EXCLUSIVE MODE;
\ir ../constraints/002_tenant_assignments.sql
\ir ../constraints/003_tenant_area_relations.sql
COMMIT;
