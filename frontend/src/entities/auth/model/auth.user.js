function decodeJwtPayload(token) {
  try {
    const payload = token.split(".")[1];
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const decoded = decodeURIComponent(
      atob(normalized)
        .split("")
        .map((char) => `%${`00${char.charCodeAt(0).toString(16)}`.slice(-2)}`)
        .join(""),
    );
    return JSON.parse(decoded);
  } catch {
    return {};
  }
}

export function normalizeAuthUser(payload = {}, fallbackUsername = "") {
  const source = payload.user || payload;
  const groups = source.groups || source.grupos || [];
  const memberships = source.tenant_memberships || source.memberships || [];
  const activeTenant = source.active_tenant || source.activeTenant || memberships[0] || null;
  const permissions = source.active_permissions || source.permissions || source.permisos || activeTenant?.permissions || [];
  const username = source.username || fallbackUsername;
  const displayName = source.display_name || [source.first_name, source.last_name].filter(Boolean).join(" ") || username;

  return {
    id: source.id || source.user_id || null,
    username,
    email: source.email || "",
    firstName: source.first_name || "",
    lastName: source.last_name || "",
    displayName,
    isStaff: Boolean(source.is_staff),
    isSuperuser: Boolean(source.is_superuser),
    groups,
    permissions,
    roles: source.roles || memberships.map((membership) => membership.role).filter(Boolean) || (source.is_staff || source.is_superuser ? ["admin"] : groups),
    tenantMemberships: memberships,
    activeTenant,
    activeTenantId: source.active_tenant_id || activeTenant?.tenant_id || activeTenant?.tenant || null,
    activeTenantRole: source.active_tenant_role || activeTenant?.role || null,
    activeAreaId: source.active_area_id || activeTenant?.area_id || activeTenant?.area || null,
  };
}

export function userFromAccessToken(accessToken, fallbackUsername = "") {
  return normalizeAuthUser(decodeJwtPayload(accessToken || ""), fallbackUsername);
}

export function userStorageScope(user) {
  return [user?.activeTenantId, user?.id || user?.username || "anonymous"].filter(Boolean).join(":");
}

export function hasTenantPermission(user, permission) {
  if (!permission) return true;
  if (user?.isSuperuser || user?.permissions?.includes("*")) return true;
  return (user?.permissions || []).includes(permission);
}

export function isTenantAdmin(user) {
  return Boolean(user?.isSuperuser || user?.activeTenantRole === "TENANT_ADMIN");
}
