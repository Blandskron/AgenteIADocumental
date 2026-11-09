-- Synthetic public-schema fixtures always rolled back. Run in a dedicated test DB.
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL statement_timeout = '30s';
CREATE FUNCTION pg_temp.assert_tenant_report(report jsonb, baseline jsonb, expected jsonb) RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
    IF report->>'version' <> '1' OR report->>'scope' <> 'tenant_relationships'
       OR jsonb_typeof(report->'checks') <> 'object'
       OR (SELECT count(*) FROM jsonb_object_keys(report->'checks')) <> 13
       OR report->>'requires_review' <> ((report->>'issues')::bigint > 0)::text
       OR report::text LIKE '%synthetic-private%' THEN
        RAISE EXCEPTION 'Invalid tenant report contract';
    END IF;
    IF EXISTS (SELECT 1 FROM jsonb_each(report->'checks') e
       WHERE e.value::bigint - (baseline->'checks'->e.key)::bigint
             <> COALESCE((expected->e.key)::bigint, 0)) THEN
        RAISE EXCEPTION 'Unexpected tenant preflight counts';
    END IF;
END $$;

\ir ../checks/tenant_preflight_report.sql
\set baseline_tenant_report :tenant_report
SELECT gen_random_uuid()::text AS marker \gset
INSERT INTO public.auth_user(username,password,first_name,last_name,email,is_superuser,is_staff,is_active,date_joined)
VALUES (:'marker','synthetic-private','','','',false,false,true,now()) RETURNING id AS user_id \gset
INSERT INTO public.tenants(tenant_id,name) VALUES (:'marker'||'-a','synthetic-private'),(:'marker'||'-b','synthetic-private');
INSERT INTO public.tenant_areas(area_id,tenant_id,name,parent_area_id) VALUES
  (:'marker'||'-a1',:'marker'||'-a','synthetic-private',NULL),
  (:'marker'||'-a2',:'marker'||'-a','synthetic-private',:'marker'||'-a1'),
  (:'marker'||'-b1',:'marker'||'-b','synthetic-private',NULL);
INSERT INTO public.tenant_memberships(tenant_id,user_id,area_id,role)
VALUES (:'marker'||'-a',:'user_id',:'marker'||'-a1','USER');
INSERT INTO public.tenant_groups(group_id,tenant_id,name)
VALUES (:'marker'||'-g1',:'marker'||'-a','synthetic-private'),(:'marker'||'-g2',:'marker'||'-b','synthetic-private');
INSERT INTO public.tenant_user_groups(tenant_id,user_id,group_id)
VALUES (:'marker'||'-a',:'user_id',:'marker'||'-g1');
INSERT INTO public.documents(document_id,tenant_id,owner_area_id,filename,storage_path,mime_type)
VALUES (:'marker'||'-d1',:'marker'||'-a',:'marker'||'-a1','synthetic-private','synthetic-private','text/plain'),
       (:'marker'||'-global',NULL,NULL,'synthetic-private','synthetic-private','text/plain');
\ir ../checks/tenant_preflight_report.sql
SELECT pg_temp.assert_tenant_report(:'tenant_report', :'baseline_tenant_report', '{}');

-- Cross-tenant relationships are still legal in today's schema, hence PLAT-001.
UPDATE public.tenant_areas SET parent_area_id=:'marker'||'-b1' WHERE area_id=:'marker'||'-a2';
UPDATE public.tenant_memberships SET area_id=:'marker'||'-b1' WHERE tenant_id=:'marker'||'-a';
UPDATE public.documents SET owner_area_id=:'marker'||'-b1' WHERE document_id=:'marker'||'-d1';
INSERT INTO public.documents(document_id,owner_area_id,filename,storage_path,mime_type)
VALUES (:'marker'||'-d2',:'marker'||'-a1','synthetic-private','synthetic-private','text/plain');
INSERT INTO public.tenant_user_groups(tenant_id,user_id,group_id)
VALUES (:'marker'||'-a',:'user_id',:'marker'||'-g2'),(:'marker'||'-a',:'marker',:'marker'||'-g1');
INSERT INTO public.tenant_memberships(tenant_id,user_id,role) VALUES (:'marker'||'-b',:'marker','USER');
\ir ../checks/tenant_preflight_report.sql
SELECT pg_temp.assert_tenant_report(:'tenant_report', :'baseline_tenant_report',
  '{"area_parent_invalid":1,"membership_area_invalid":1,"document_area_invalid":2,
    "assignment_group_invalid":1,"assignment_without_membership":1,"membership_user_missing":1}');

-- Two-node cycle, self-cycle and an area that reaches a cycle; a bounded deep chain.
UPDATE public.tenant_areas SET parent_area_id=:'marker'||'-a1' WHERE area_id=:'marker'||'-a2';
UPDATE public.tenant_areas SET parent_area_id=:'marker'||'-a2' WHERE area_id=:'marker'||'-a1';
INSERT INTO public.tenant_areas(area_id,tenant_id,name,parent_area_id)
VALUES (:'marker'||'-self',:'marker'||'-a','synthetic-private',:'marker'||'-self'),
       (:'marker'||'-feeder',:'marker'||'-a','synthetic-private-feeder',:'marker'||'-a1');
INSERT INTO public.tenant_areas(area_id,tenant_id,name,parent_area_id)
SELECT :'marker'||'-depth-'||n, :'marker'||'-b', 'synthetic-private-'||n,
       CASE WHEN n>1 THEN :'marker'||'-depth-'||(n-1) ELSE NULL END
FROM generate_series(1,257) n;
\ir ../checks/tenant_preflight_report.sql
SELECT pg_temp.assert_tenant_report(:'tenant_report', :'baseline_tenant_report',
  '{"membership_area_invalid":1,"document_area_invalid":2,"assignment_group_invalid":1,
    "assignment_without_membership":1,"membership_user_missing":1,"area_cycle_reachable":4,"area_depth_unresolved":1}');

-- Simulate an incomplete restore inside this uncommitted test transaction only.
SET LOCAL session_replication_role = replica;
INSERT INTO public.tenant_areas(area_id,tenant_id,name,parent_area_id)
VALUES (:'marker'||'-missing',:'marker','synthetic-private',:'marker');
INSERT INTO public.tenant_memberships(tenant_id,user_id,area_id,role)
VALUES (:'marker',:'user_id',:'marker','USER');
INSERT INTO public.tenant_groups(group_id,tenant_id,name) VALUES (:'marker'||'-missing-group',:'marker','synthetic-private');
INSERT INTO public.tenant_group_permissions(group_id,permission_code) VALUES (:'marker','synthetic-private');
INSERT INTO public.documents(document_id,tenant_id,filename,storage_path,mime_type)
VALUES (:'marker'||'-missing-tenant',:'marker','synthetic-private','synthetic-private','text/plain');
SET LOCAL session_replication_role = origin;
\ir ../checks/tenant_preflight_report.sql
SELECT pg_temp.assert_tenant_report(:'tenant_report', :'baseline_tenant_report',
  '{"area_tenant_missing":1,"area_parent_invalid":1,"membership_tenant_missing":1,
    "membership_area_invalid":2,"membership_user_missing":1,"document_tenant_missing":1,
    "document_area_invalid":2,"group_tenant_missing":1,"permission_group_missing":1,
    "assignment_group_invalid":1,"assignment_without_membership":1,"area_cycle_reachable":4,"area_depth_unresolved":1}');
ROLLBACK;
\echo 'Tenant preflight: valid/global, cross-tenant, orphan, cycles/depth and privacy checks passed; fixtures rolled back.'
