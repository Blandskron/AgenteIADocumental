interface GroupForm {
  name: string;
  description?: string;
  permissions?: string[];
}
import type { MaybeClient } from "@/shared/api/types.ts";
import { requireClient } from "@/shared/api/types.ts";
interface TenantDto {
  tenant_id?: string;
  id?: string;
  name?: string;
  tax_id?: string;
  status?: string;
  metadata?: Record<string, unknown>;
}
interface AreaDto {
  area_id?: string;
  id?: string;
  tenant?: string;
  tenant_id?: string;
  name?: string;
  parent_area?: string;
  parent_area_id?: string;
}
interface MembershipDto {
  membership_id?: string;
  id?: string;
  tenant?: string;
  tenant_id?: string;
  tenant_name?: string;
  user_id?: string;
  area?: string;
  area_id?: string;
  area_name?: string;
  role?: string;
  status?: string;
  permissions?: string[];
}
interface TenantGroupDto {
  group_id?: string;
  id?: string;
  tenant?: string;
  tenant_id?: string;
  name?: string;
  description?: string;
  is_system?: boolean;
  permission_codes?: string[];
  permissions?: string[];
}
interface TenantUserGroupDto {
  tenant?: string;
  tenant_id?: string;
  user_id?: string;
  group?: string;
  group_id?: string;
  group_name?: string;
}
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

function asArray<T>(payload: unknown): T[] {
  if (Array.isArray(payload)) return payload as T[];
  if (
    typeof payload === "object" &&
    payload !== null &&
    "results" in payload &&
    Array.isArray(payload.results)
  )
    return payload.results as T[];
  return [];
}

export function normalizeTenant(tenant: TenantDto = {}) {
  return {
    tenantId: tenant.tenant_id || tenant.id || "",
    name: tenant.name || "",
    taxId: tenant.tax_id || "",
    status: tenant.status || "ACTIVE",
    metadata: tenant.metadata || {},
  };
}

export function normalizeArea(area: AreaDto = {}) {
  return {
    areaId: area.area_id || area.id || "",
    tenantId: area.tenant || area.tenant_id || "",
    name: area.name || "",
    parentAreaId: area.parent_area || area.parent_area_id || "",
  };
}

export function normalizeMembership(membership: MembershipDto = {}) {
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

export function normalizeTenantGroup(group: TenantGroupDto = {}) {
  return {
    groupId: group.group_id || group.id || "",
    tenantId: group.tenant || group.tenant_id || "",
    name: group.name || "",
    description: group.description || "",
    isSystem: Boolean(group.is_system),
    permissions: group.permission_codes || group.permissions || [],
  };
}

export function normalizeTenantUserGroup(row: TenantUserGroupDto = {}) {
  return {
    tenantId: row.tenant || row.tenant_id || "",
    userId: String(row.user_id || ""),
    groupId: row.group || row.group_id || "",
    groupName: row.group_name || "",
  };
}

export function listTenants(apiClient: MaybeClient) {
  return requireClient(apiClient)("/api/users/tenants/", {
    method: "GET",
  }).then((payload) => asArray<TenantDto>(payload).map(normalizeTenant));
}

export function createTenant(
  apiClient: MaybeClient,
  form: { name: string; taxId?: string; status?: string },
) {
  return requireClient(apiClient)<Parameters<typeof normalizeTenant>[0]>(
    "/api/users/tenants/",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: form.name,
        tax_id: form.taxId || null,
        status: form.status || "ACTIVE",
      }),
    },
  ).then(normalizeTenant);
}

export function listTenantAreas(apiClient: MaybeClient) {
  return requireClient(apiClient)("/api/users/tenant-areas/", {
    method: "GET",
  }).then((payload) => asArray<AreaDto>(payload).map(normalizeArea));
}

export function createTenantArea(
  apiClient: MaybeClient,
  form: { tenantId: string; name: string; parentAreaId?: string },
) {
  return requireClient(apiClient)<Parameters<typeof normalizeArea>[0]>(
    "/api/users/tenant-areas/",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tenant: form.tenantId,
        name: form.name,
        parent_area: form.parentAreaId || null,
      }),
    },
  ).then(normalizeArea);
}

export function listTenantMemberships(apiClient: MaybeClient) {
  return requireClient(apiClient)("/api/users/tenant-memberships/", {
    method: "GET",
  }).then((payload) =>
    asArray<MembershipDto>(payload).map(normalizeMembership),
  );
}

export function provisionTenantUser(
  apiClient: MaybeClient,
  form: {
    tenantId: string;
    username: string;
    email: string;
    firstName: string;
    lastName: string;
    password: string;
    areaId?: string;
    role: string;
  },
) {
  return requireClient(apiClient)<Parameters<typeof normalizeMembership>[0]>(
    "/api/users/tenant-memberships/provision/",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tenant: form.tenantId,
        username: form.username,
        email: form.email,
        first_name: form.firstName,
        last_name: form.lastName,
        password: form.password,
        area: form.areaId || null,
        role: form.role,
      }),
    },
  ).then(normalizeMembership);
}

export function updateTenantMembership(
  apiClient: MaybeClient,
  membershipId: string,
  form: { areaId?: string; role: string; status?: string },
) {
  return requireClient(apiClient)<Parameters<typeof normalizeMembership>[0]>(
    `/api/users/tenant-memberships/${membershipId}/`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        area: form.areaId || null,
        role: form.role,
        status: form.status || "ACTIVE",
      }),
    },
  ).then(normalizeMembership);
}

export function listTenantGroups(apiClient: MaybeClient) {
  return requireClient(apiClient)("/api/users/tenant-groups/", {
    method: "GET",
  }).then((payload) =>
    asArray<TenantGroupDto>(payload).map(normalizeTenantGroup),
  );
}

export function createTenantGroup(
  apiClient: MaybeClient,
  form: GroupForm & { tenantId: string },
) {
  return requireClient(apiClient)<Parameters<typeof normalizeTenantGroup>[0]>(
    "/api/users/tenant-groups/",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tenant: form.tenantId,
        name: form.name,
        description: form.description || "",
        permissions: form.permissions || [],
      }),
    },
  ).then(normalizeTenantGroup);
}

export function updateTenantGroup(
  apiClient: MaybeClient,
  groupId: string,
  form: GroupForm,
) {
  return requireClient(apiClient)<Parameters<typeof normalizeTenantGroup>[0]>(
    `/api/users/tenant-groups/${groupId}/`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: form.name,
        description: form.description || "",
        permissions: form.permissions || [],
      }),
    },
  ).then(normalizeTenantGroup);
}

export function assignTenantUserGroup(
  apiClient: MaybeClient,
  form: { tenantId: string; userId: string; groupId: string },
) {
  return requireClient(apiClient)<
    Parameters<typeof normalizeTenantUserGroup>[0]
  >("/api/users/tenant-user-groups/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      tenant: form.tenantId,
      user_id: String(form.userId),
      group: form.groupId,
    }),
  }).then(normalizeTenantUserGroup);
}

export function listTenantUserGroups(apiClient: MaybeClient) {
  return requireClient(apiClient)("/api/users/tenant-user-groups/", {
    method: "GET",
  }).then((payload) =>
    asArray<TenantUserGroupDto>(payload).map(normalizeTenantUserGroup),
  );
}
