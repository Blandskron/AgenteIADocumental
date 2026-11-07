function normalizeUser(user = {}) {
  return {
    id: String(user.id),
    username: user.username || "",
    email: user.email || "",
    firstName: user.first_name || "",
    lastName: user.last_name || "",
    isStaff: Boolean(user.is_staff),
    isSuperuser: Boolean(user.is_superuser),
    isActive: user.is_active !== false,
    groups: user.group_names || [],
    permissions: user.permission_ids || [],
    permissionNames: user.permission_names || [],
  };
}

function normalizeGroup(group = {}) {
  return {
    id: group.id,
    name: group.name || "",
    permissions: group.permission_ids || [],
    permissionNames: group.permission_names || [],
  };
}

function normalizePermission(permission = {}) {
  return {
    id: permission.id,
    name: permission.name || "",
    codename: permission.codename || "",
    appLabel: permission.app_label || "",
    model: permission.model || "",
  };
}

function userPayload(form) {
  return {
    username: form.username,
    email: form.email,
    first_name: form.firstName,
    last_name: form.lastName,
    password: form.password || undefined,
    role: form.role,
    is_active: form.isActive,
    groups: form.groups,
    user_permissions: form.permissions,
  };
}

export function listUsers(apiClient) {
  return apiClient("/api/users/crud/", { method: "GET" }).then((payload) =>
    (Array.isArray(payload) ? payload : payload?.results || []).map(normalizeUser),
  );
}

export function createUser(apiClient, form) {
  return apiClient("/api/users/crud/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(userPayload(form)),
  }).then(normalizeUser);
}

export function updateUser(apiClient, userId, form) {
  return apiClient(`/api/users/crud/${userId}/`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(userPayload(form)),
  }).then(normalizeUser);
}

export function deleteUser(apiClient, userId) {
  return apiClient(`/api/users/crud/${userId}/`, { method: "DELETE" });
}

export function listGroups(apiClient) {
  return apiClient("/api/users/groups/", { method: "GET" }).then((payload) =>
    Array.isArray(payload) ? payload.map(normalizeGroup) : [],
  );
}

export function createGroup(apiClient, form) {
  return apiClient("/api/users/groups/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: form.name, permissions: form.permissions }),
  }).then(normalizeGroup);
}

export function updateGroup(apiClient, groupId, form) {
  return apiClient(`/api/users/groups/${groupId}/`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: form.name, permissions: form.permissions }),
  }).then(normalizeGroup);
}

export function deleteGroup(apiClient, groupId) {
  return apiClient(`/api/users/groups/${groupId}/`, { method: "DELETE" });
}

export function listPermissions(apiClient) {
  return apiClient("/api/users/permissions/", { method: "GET" }).then((payload) =>
    Array.isArray(payload) ? payload.map(normalizePermission) : [],
  );
}

export function changePassword(apiClient, oldPassword, newPassword, signal) {
  return apiClient("/api/users/change-password/", {
    method: "POST",
    signal,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      old_password: oldPassword,
      new_password: newPassword,
    }),
  });
}
