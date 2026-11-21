import type { MaybeClient } from "@/shared/api/types.ts";
import { requireClient } from "@/shared/api/types.ts";

export interface AuditLogEntry {
  audit_id: string;
  tenant_id: string | null;
  actor_user_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  target_user_id: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface AuditLogPage {
  total: number;
  limit: number;
  offset: number;
  items: AuditLogEntry[];
}

export function fetchAuditLogs(
  authClient: MaybeClient,
  {
    action,
    resourceType,
    limit = 25,
    offset = 0,
  }: {
    action?: string;
    resourceType?: string;
    limit?: number;
    offset?: number;
  } = {},
) {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  if (action) params.set("action", action);
  if (resourceType) params.set("resource_type", resourceType);
  return requireClient(authClient)<AuditLogPage>(
    `/api/audit-logs/?${params.toString()}`,
    { method: "GET" },
  );
}

