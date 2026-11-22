import assert from "node:assert/strict";
import test from "node:test";

import { fetchAuditLogs } from "../src/features/audit-logs/api/audit-logs.api.ts";

test("fetchAuditLogs builds query params, forwards AbortSignal, and normalizes items", async () => {
  const calls = [];
  const controller = new AbortController();
  const client = async (path, options) => {
    calls.push({ path, options });
    return {
      total: 1,
      limit: 10,
      offset: 0,
      items: [{ audit_id: "a1", action: "ai_settings_write" }],
    };
  };

  const page = await fetchAuditLogs(client, {
    action: "ai_settings_write",
    resourceType: "tenant_integration",
    limit: 10,
    offset: 0,
    signal: controller.signal,
  });
  assert.equal(page.total, 1);
  assert.equal(
    calls[0].path,
    "/api/audit-logs/?limit=10&offset=0&action=ai_settings_write&resource_type=tenant_integration",
  );
  assert.equal(calls[0].options.method, "GET");
  assert.equal(calls[0].options.signal, controller.signal);

  const emptyPage = await fetchAuditLogs(async () => ({}), {});
  assert.deepEqual(emptyPage.items, []);
  assert.equal(emptyPage.total, 0);
});

