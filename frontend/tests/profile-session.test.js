import assert from "node:assert/strict";
import test from "node:test";
import { createProfileSessionClient } from "../src/features/profile/api/session-client.ts";
import { normalizeAuthUser } from "../src/entities/auth/model/auth.user.ts";

test("refresh reuses a session client and newer requests use its latest credential", async () => {
  const original = global.fetch, seen = [];
  const session = { key: "one", auth: { access: "expired" }, logout: () => assert.fail("unexpected logout"),
    refreshAccessToken: async () => { session.auth.access = "renewed"; return "renewed"; } };
  global.fetch = async (_, options) => {
    seen.push(options.headers.get("Authorization"));
    return Response.json({}, { status: seen.length === 1 ? 401 : 200 });
  };
  try {
    const client = createProfileSessionClient("https://synthetic.invalid", "one", () => session);
    await client("/profile"); await client("/profile");
    assert.deepEqual(seen, ["Bearer expired", "Bearer renewed", "Bearer renewed"]);
  } finally { global.fetch = original; }
});

test("late 401 from a previous account cannot refresh, retry or log out the new account", async () => {
  const original = global.fetch; let finish;
  let session = { key: "old", auth: { access: "old" }, refreshAccessToken: () => assert.fail("stale refresh"), logout: () => assert.fail("stale logout") };
  global.fetch = () => new Promise((resolve) => { finish = resolve; });
  try {
    const client = createProfileSessionClient("https://synthetic.invalid", "old", () => session);
    const pending = client("/profile"); session = { ...session, key: "new" };
    finish(Response.json({}, { status: 401 }));
    await assert.rejects(pending, { name: "AbortError" });
    await assert.rejects(client("/profile"), { name: "AbortError" });
  } finally { global.fetch = original; }
});

test("concurrent unauthorized profile reads share one refresh", async () => {
  const original = global.fetch; let refreshes = 0;
  const session = { key: "one", auth: { access: "expired" }, refreshAccessToken: async () => {
    refreshes++; await new Promise((resolve) => setImmediate(resolve)); session.auth.access = "renewed"; return "renewed";
  } };
  global.fetch = async (_, options) => Response.json({}, { status: options.headers.get("Authorization") === "Bearer expired" ? 401 : 200 });
  try {
    const client = createProfileSessionClient("https://synthetic.invalid", "one", () => session);
    await Promise.all([client("/one"), client("/two")]); assert.equal(refreshes, 1);
  } finally { global.fetch = original; }
});

test("tenant identity and effective permissions come from the selected Auth membership", () => {
  const user = normalizeAuthUser({ id: 1, is_staff: true, permissions: ["global.change_user"], active_tenant_id: "selected",
    active_role: "USER", active_permissions: [], tenant_memberships: [{ tenant_id: "other", role: "TENANT_ADMIN" },
      { tenant_id: "selected", role: "USER", groups: ["synthetic"] }] });
  assert.equal(user.activeTenant.tenant_id, "selected"); assert.equal(user.activeTenantRole, "USER");
  assert.deepEqual(user.permissions, []);
  assert.deepEqual(normalizeAuthUser({ id: 1, is_staff: true, permissions: ["global.change_user"] }).permissions, []);
});

test("a successful response belonging to an old session is discarded", async () => {
  const original = global.fetch; let finish;
  let session = { key: "one", auth: { access: "synthetic" } };
  global.fetch = () => new Promise((resolve) => { finish = resolve; });
  try {
    const client = createProfileSessionClient("https://synthetic.invalid", "one", () => session);
    const pending = client("/profile"); session = { key: "two" };
    finish(Response.json({ email: "old@example.com" }));
    await assert.rejects(pending, { name: "AbortError" });
  } finally { global.fetch = original; }
});
