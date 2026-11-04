-- Read-only preflight for tightening tenant relationships in a later migration.
SELECT 'area_parent_cross_tenant' AS check_name, count(*) AS inconsistent_rows
FROM tenant_areas child
JOIN tenant_areas parent ON parent.area_id = child.parent_area_id
WHERE child.tenant_id <> parent.tenant_id
UNION ALL
SELECT 'membership_area_cross_tenant', count(*)
FROM tenant_memberships membership
JOIN tenant_areas area ON area.area_id = membership.area_id
WHERE membership.tenant_id <> area.tenant_id
UNION ALL
SELECT 'document_area_cross_tenant', count(*)
FROM documents document
JOIN tenant_areas area ON area.area_id = document.owner_area_id
WHERE document.tenant_id IS DISTINCT FROM area.tenant_id
UNION ALL
SELECT 'assignment_group_cross_tenant', count(*)
FROM tenant_user_groups assignment
JOIN tenant_groups tenant_group ON tenant_group.group_id = assignment.group_id
WHERE assignment.tenant_id <> tenant_group.tenant_id
UNION ALL
SELECT 'assignment_without_membership', count(*)
FROM tenant_user_groups assignment
WHERE NOT EXISTS (
    SELECT 1 FROM tenant_memberships membership
    WHERE membership.tenant_id = assignment.tenant_id AND membership.user_id = assignment.user_id
);
