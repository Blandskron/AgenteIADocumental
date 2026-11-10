import type { normalizeAuthUser } from "./auth.user.ts";
export interface TenantMembership {
  tenant_id?: string;
  tenant?: string;
  tenant_name?: string;
  name?: string;
  role?: string;
  area_id?: string;
  area?: string;
  area_name?: string;
  groups?: string[];
  permissions?: string[];
}
export interface AuthUserPayload {
  id?: number | string;
  user_id?: number | string;
  username?: string;
  email?: string;
  first_name?: string;
  last_name?: string;
  display_name?: string;
  is_staff?: boolean;
  is_superuser?: boolean;
  groups?: string[];
  grupos?: string[];
  roles?: string[];
  tenant_memberships?: TenantMembership[];
  memberships?: TenantMembership[];
  active_tenant?: TenantMembership;
  activeTenant?: TenantMembership;
  active_tenant_id?: string;
  active_permissions?: string[];
  active_role?: string;
  active_tenant_role?: string;
  active_area_id?: string;
}
export interface AuthPayload extends AuthUserPayload {
  user?: AuthUserPayload;
}
export interface TokenPayload extends AuthPayload {
  access: string;
  refresh: string;
}
export interface Credentials {
  username: string;
  password: string;
}
export type AuthUser = ReturnType<typeof normalizeAuthUser>;
export interface AuthSession {
  sessionId: string;
  access: string;
  refresh: string;
  username: string;
  user: AuthUser;
}
