-- Aggregate-only snapshot. Run after the shared schema and Django Auth migrations.
-- No writes, IDs, names, documents, credentials or automatic repairs in the report.
WITH RECURSIVE area_walk(start_id, next_id, path, cycle, depth) AS (
    SELECT area_id, parent_area_id, ARRAY[area_id], false, 1
    FROM public.tenant_areas WHERE parent_area_id IS NOT NULL
    UNION ALL
    SELECT w.start_id, p.parent_area_id, w.path || p.area_id,
           p.area_id = ANY(w.path), w.depth + 1
    FROM area_walk w JOIN public.tenant_areas p ON p.area_id = w.next_id
    WHERE NOT w.cycle AND w.depth < 256
), checks AS (
    SELECT 'area_tenant_missing' AS name, count(*) AS affected_rows
    FROM public.tenant_areas a LEFT JOIN public.tenants t USING (tenant_id)
    WHERE t.tenant_id IS NULL
    UNION ALL
    SELECT 'area_parent_invalid', count(*)
    FROM public.tenant_areas a LEFT JOIN public.tenant_areas p ON p.area_id = a.parent_area_id
    WHERE a.parent_area_id IS NOT NULL AND (p.area_id IS NULL OR a.tenant_id <> p.tenant_id)
    UNION ALL
    SELECT 'membership_tenant_missing', count(*)
    FROM public.tenant_memberships m LEFT JOIN public.tenants t USING (tenant_id)
    WHERE t.tenant_id IS NULL
    UNION ALL
    SELECT 'membership_area_invalid', count(*)
    FROM public.tenant_memberships m LEFT JOIN public.tenant_areas a ON a.area_id = m.area_id
    WHERE m.area_id IS NOT NULL AND (a.area_id IS NULL OR m.tenant_id <> a.tenant_id)
    UNION ALL
    SELECT 'membership_user_missing', count(*)
    FROM public.tenant_memberships m LEFT JOIN public.auth_user u ON u.id::text = m.user_id
    WHERE u.id IS NULL
    UNION ALL
    SELECT 'document_tenant_missing', count(*)
    FROM public.documents d LEFT JOIN public.tenants t USING (tenant_id)
    WHERE d.tenant_id IS NOT NULL AND t.tenant_id IS NULL
    UNION ALL
    SELECT 'document_area_invalid', count(*)
    FROM public.documents d LEFT JOIN public.tenant_areas a ON a.area_id = d.owner_area_id
    WHERE d.owner_area_id IS NOT NULL AND (a.area_id IS NULL OR d.tenant_id IS DISTINCT FROM a.tenant_id)
    UNION ALL
    SELECT 'group_tenant_missing', count(*)
    FROM public.tenant_groups g LEFT JOIN public.tenants t USING (tenant_id)
    WHERE t.tenant_id IS NULL
    UNION ALL
    SELECT 'permission_group_missing', count(*)
    FROM public.tenant_group_permissions p LEFT JOIN public.tenant_groups g USING (group_id)
    WHERE g.group_id IS NULL
    UNION ALL
    SELECT 'assignment_group_invalid', count(*)
    FROM public.tenant_user_groups a LEFT JOIN public.tenant_groups g USING (group_id)
    WHERE g.group_id IS NULL OR a.tenant_id <> g.tenant_id
    UNION ALL
    SELECT 'assignment_without_membership', count(*)
    FROM public.tenant_user_groups a
    WHERE NOT EXISTS (SELECT 1 FROM public.tenant_memberships m WHERE m.tenant_id = a.tenant_id AND m.user_id = a.user_id)
    UNION ALL
    SELECT 'area_cycle_reachable', count(DISTINCT start_id) FROM area_walk WHERE cycle
    UNION ALL
    SELECT 'area_depth_unresolved', count(DISTINCT start_id) FROM area_walk
    WHERE depth = 256 AND next_id IS NOT NULL AND NOT cycle
)
SELECT jsonb_build_object(
    'version', 1,
    'scope', 'tenant_relationships',
    'checks', jsonb_object_agg(name, affected_rows ORDER BY name),
    'issues', sum(affected_rows),
    'requires_review', bool_or(affected_rows > 0)
) AS tenant_report FROM checks
\gset
