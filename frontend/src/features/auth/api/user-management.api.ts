interface UserForm {
  username: string;
  email: string;
  firstName: string;
  lastName: string;
  password?: string;
  role?: string;
  isActive?: boolean;
  groups?: string[];
  permissions?: number[];
}
interface GroupForm {
  name: string;
  permissions?: number[];
}
import type { MaybeClient } from "@/shared/api/types.ts";
import { requireClient } from "@/shared/api/types.ts";
interface UserDto {
  id?: string;
  username?: string;
  email?: string;
  first_name?: string;
  last_name?: string;
  is_staff?: boolean;
  is_superuser?: boolean;
  is_active?: boolean;
  group_names?: string[];
  permission_ids?: number[];
  permission_names?: string[];
}
interface GroupDto {
  id?: string;
  name?: string;
  permission_ids?: number[];
  permission_names?: string[];
}
interface PermissionDto {
  id?: string;
  name?: string;
  codename?: string;
  app_label?: string;
  model?: string;
}
function normalizeUser(user: UserDto = {}) {
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

function normalizeGroup(group: GroupDto = {}) {
  return {
    id: group.id,
    name: group.name || "",
    permissions: group.permission_ids || [],
    permissionNames: group.permission_names || [],
  };
}

function normalizePermission(permission: PermissionDto = {}) {
  return {
    id: permission.id,
    name: permission.name || "",
    codename: permission.codename || "",
    appLabel: permission.app_label || "",
    model: permission.model || "",
  };
}

function userPayload(form: UserForm) {
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

export function listUsers(apiClient: MaybeClient) {
  return requireClient(apiClient)<UserDto[] | { results: UserDto[] }>(
    "/api/users/crud/",
    { method: "GET" },
  ).then((payload) =>
    (Array.isArray(payload) ? payload : payload?.results || []).map(
      normalizeUser,
    ),
  );
}

export function createUser(apiClient: MaybeClient, form: UserForm) {
  return requireClient(apiClient)<Parameters<typeof normalizeUser>[0]>(
    "/api/users/crud/",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(userPayload(form)),
    },
  ).then(normalizeUser);
}

export function updateUser(
  apiClient: MaybeClient,
  userId: string,
  form: UserForm,
) {
  return requireClient(apiClient)<Parameters<typeof normalizeUser>[0]>(
    `/api/users/crud/${userId}/`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(userPayload(form)),
    },
  ).then(normalizeUser);
}

export function deleteUser(apiClient: MaybeClient, userId: string) {
  return requireClient(apiClient)(`/api/users/crud/${userId}/`, {
    method: "DELETE",
  });
}

export function listGroups(apiClient: MaybeClient) {
  return requireClient(apiClient)("/api/users/groups/", { method: "GET" }).then(
    (payload) => (Array.isArray(payload) ? payload.map(normalizeGroup) : []),
  );
}

export function createGroup(apiClient: MaybeClient, form: GroupForm) {
  return requireClient(apiClient)<Parameters<typeof normalizeGroup>[0]>(
    "/api/users/groups/",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: form.name, permissions: form.permissions }),
    },
  ).then(normalizeGroup);
}

export function updateGroup(
  apiClient: MaybeClient,
  groupId: string,
  form: GroupForm,
) {
  return requireClient(apiClient)<Parameters<typeof normalizeGroup>[0]>(
    `/api/users/groups/${groupId}/`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: form.name, permissions: form.permissions }),
    },
  ).then(normalizeGroup);
}

export function deleteGroup(apiClient: MaybeClient, groupId: string) {
  return requireClient(apiClient)(`/api/users/groups/${groupId}/`, {
    method: "DELETE",
  });
}

export function listPermissions(apiClient: MaybeClient) {
  return requireClient(apiClient)("/api/users/permissions/", {
    method: "GET",
  }).then((payload) =>
    Array.isArray(payload) ? payload.map(normalizePermission) : [],
  );
}

export function changePassword(
  apiClient: MaybeClient,
  oldPassword: string,
  newPassword: string,
  signal?: AbortSignal,
) {
  return requireClient(apiClient)("/api/users/change-password/", {
    method: "POST",
    signal,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      old_password: oldPassword,
      new_password: newPassword,
    }),
  });
}
