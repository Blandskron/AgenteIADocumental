const TENANT_PERMISSION_OPTIONS = [
  "view_documents",
  "upload_documents",
  "download_documents",
  "assign_documents",
  "approve_documents",
  "reject_documents",
  "sign_documents",
  "manage_documents",
  "manage_users",
  "manage_areas",
  "manage_groups",
  "use_chat",
  "use_google_drive",
  "use_sharepoint",
  "view_audit_logs",
];

export { TENANT_PERMISSION_OPTIONS };

function asArray(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.results)) return payload.results;
  return [];
}

export function normalizeTenant(tenant = {}) {
  return {
    tenantId: tenant.tenant_id || tenant.id || "",
    name: tenant.name || "",
    taxId: tenant.tax_id || "",
    status: tenant.status || "ACTIVE",
    metadata: tenant.metadata || {},
  };
}

export function normalizeArea(area = {}) {
  return {
    areaId: area.area_id || area.id || "",
    tenantId: area.tenant || area.tenant_id || "",
    name: area.name || "",
    parentAreaId: area.parent_area || area.parent_area_id || "",
  };
}

export function normalizeMembership(membership = {}) {
  return {
    membershipId: membership.membership_id || membership.id || "",
    tenantId: membership.tenant || membership.tenant_id || "",
    tenantName: membership.tenant_name || "",
    userId: String(membership.user_id || ""),
    areaId: membership.area || membership.area_id || "",
    areaName: membership.area_name || "",
    role: membership.role || "USER",
    status: membership.status || "ACTIVE",
    permissions: membership.permissions || [],
  };
}

export function normalizeTenantGroup(group = {}) {
  return {
    groupId: group.group_id || group.id || "",
    tenantId: group.tenant || group.tenant_id || "",
    name: group.name || "",
    description: group.description || "",
    isSystem: Boolean(group.is_system),
    permissions: group.permission_codes || group.permissions || [],
  };
}

export function normalizeTenantUserGroup(row = {}) {
  return {
    tenantId: row.tenant || row.tenant_id || "",
    userId: String(row.user_id || ""),
    groupId: row.group || row.group_id || "",
    groupName: row.group_name || "",
  };
}

export function listTenants(apiClient) {
  return apiClient("/api/users/tenants/", { method: "GET" }).then((payload) => asArray(payload).map(normalizeTenant));
}

export function createTenant(apiClient, form) {
  return apiClient("/api/users/tenants/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: form.name, tax_id: form.taxId || null, status: form.status || "ACTIVE" }),
  }).then(normalizeTenant);
}

export function listTenantAreas(apiClient) {
  return apiClient("/api/users/tenant-areas/", { method: "GET" }).then((payload) => asArray(payload).map(normalizeArea));
}

export function createTenantArea(apiClient, form) {
  return apiClient("/api/users/tenant-areas/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tenant: form.tenantId, name: form.name, parent_area: form.parentAreaId || null }),
  }).then(normalizeArea);
}

export function listTenantMemberships(apiClient) {
  return apiClient("/api/users/tenant-memberships/", { method: "GET" }).then((payload) =>
    asArray(payload).map(normalizeMembership),
  );
}

export function createTenantMembership(apiClient, form) {
  return apiClient("/api/users/tenant-memberships/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      tenant: form.tenantId,
      user_id: String(form.userId),
      area: form.areaId || null,
      role: form.role,
      status: form.status || "ACTIVE",
    }),
  }).then(normalizeMembership);
}

export function updateTenantMembership(apiClient, membershipId, form) {
  return apiClient(`/api/users/tenant-memberships/${membershipId}/`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      area: form.areaId || null,
      role: form.role,
      status: form.status || "ACTIVE",
    }),
  }).then(normalizeMembership);
}

export function listTenantGroups(apiClient) {
  return apiClient("/api/users/tenant-groups/", { method: "GET" }).then((payload) =>
    asArray(payload).map(normalizeTenantGroup),
  );
}

export function createTenantGroup(apiClient, form) {
  return apiClient("/api/users/tenant-groups/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      tenant: form.tenantId,
      name: form.name,
      description: form.description || "",
      permissions: form.permissions || [],
    }),
  }).then(normalizeTenantGroup);
}

export function updateTenantGroup(apiClient, groupId, form) {
  return apiClient(`/api/users/tenant-groups/${groupId}/`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: form.name,
      description: form.description || "",
      permissions: form.permissions || [],
    }),
  }).then(normalizeTenantGroup);
}

export function assignTenantUserGroup(apiClient, form) {
  return apiClient("/api/users/tenant-user-groups/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tenant: form.tenantId, user_id: String(form.userId), group: form.groupId }),
  }).then(normalizeTenantUserGroup);
}

export function listTenantUserGroups(apiClient) {
  return apiClient("/api/users/tenant-user-groups/", { method: "GET" }).then((payload) =>
    asArray(payload).map(normalizeTenantUserGroup),
  );
}
