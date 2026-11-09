\set ON_ERROR_STOP on
-- Auth's Django migrations must have completed; do not add to run_all.sql.
BEGIN;
SET LOCAL lock_timeout = '5s';
LOCK TABLE public.auth_user, public.tenants, public.tenant_areas,
    public.tenant_groups, public.tenant_memberships, public.tenant_user_groups,
    public.documents IN SHARE ROW EXCLUSIVE MODE;
\ir ../constraints/002_tenant_assignments.sql
\ir ../constraints/003_tenant_area_relations.sql
\ir ../constraints/004_tenant_hierarchy.sql
\ir ../constraints/005_tenant_user_links.sql
COMMIT;
