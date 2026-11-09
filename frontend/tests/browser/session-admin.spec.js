import { test, expect } from "@playwright/test";
import { normalizeAuthUser } from "../../src/entities/auth/model/auth.user.js";

const person = (id = 123, admin = false) => ({ id, username: `synthetic-${id}`, is_superuser: admin,
  active_tenant_id: "tenant-one", active_role: admin ? "TENANT_ADMIN" : "USER", active_permissions: ["use_chat"],
  tenant_memberships: [{ tenant_id: "tenant-one", tenant_name: "Empresa uno", role: admin ? "TENANT_ADMIN" : "USER" }] });
const access = (user, jti = "initial") => `synthetic.${Buffer.from(JSON.stringify({ ...user, jti })).toString("base64url")}.synthetic`;
const latch = () => { let release; const promise = new Promise((resolve) => { release = resolve; }); return { promise, release }; };

async function prepare(page, user, respond) {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.addInitScript(({ user, token }) => {
    window.__BLANDSKRON_CONFIG__ = Object.fromEntries(["AUTH", "PROFILE", "RAG_CHAT", "RAG_DOCUMENT", "DOCUMENT_SEARCH",
      "DOCUMENT_ACCESS", "DOCUMENT_LIBRARY", "DOCUMENT_TRANSFER", "DOCUMENT_EXPORT", "GOOGLE_DRIVE_IMPORT", "CONVERSATION"]
      .map((key) => [`VITE_${key}_BASE_URL`, `${location.origin}/test-api`]));
    localStorage.setItem("blandskron.auth", JSON.stringify({ user, access: token, refresh: "synthetic-refresh",
      username: user.username, sessionId: "11111111-1111-1111-1111-111111111111" }));
  }, { user: normalizeAuthUser(user), token: access(user) });
  await page.route("**/test-api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = (body, status = 200) => route.fulfill({ json: body, status });
    if (await respond(route, path, json)) return;
    if (path.endsWith("/me/")) return json(user);
    if (path.endsWith("/logout/")) return json({});
    if (path.endsWith("/profile")) return json({ profile_id: null, user_id: String(user.id), version: 0, additional_info: {} });
    if (path.endsWith("/transfers")) return json({ items: [], has_more: false, offset: 0, limit: 50 });
    if (path.endsWith("/conversations") && route.request().method() === "POST") return json({ conversation_id: "synthetic-conversation", title: "Chat sintético" });
    if (path.endsWith("/tenants/")) return json([{ tenant_id: "tenant-one", name: "Empresa uno" }, { tenant_id: "tenant-two", name: "Empresa dos" }]);
    return json([]);
  });
  return errors;
}

test("401s from separate services share one refresh and preserve the profile", async ({ page }) => {
  const user = person(), gate = latch(), rejected = new Set(); let refreshes = 0;
  const errors = await prepare(page, user, async (route, path, json) => {
    if (path.endsWith("/token/refresh/")) {
      refreshes++; await gate.promise;
      await json({ access: access(user, "renewed"), refresh: "next-refresh", user }); return true;
    }
    if ((path.endsWith("/me/") || path.endsWith("/profile")) && route.request().headers().authorization === `Bearer ${access(user)}`) {
      rejected.add(path); await json({ detail: "synthetic expired access" }, 401); return true;
    }
    return false;
  });
  await page.goto("/profile");
  await expect.poll(() => rejected.size).toBe(2);
  gate.release();
  await expect(page.getByLabel("Nombre Completo")).toBeVisible();
  await expect.poll(() => refreshes).toBe(1);
  expect(errors).toEqual([]);
});

test("a late rejection from the previous account cannot log out a new login", async ({ page }) => {
  const old = person(), next = person(456), gate = latch(); let pending = false, loggedIn = false;
  const errors = await prepare(page, old, async (route, path, json) => {
    if (path.endsWith("/login/")) { loggedIn = true; await json({ access: access(next), refresh: "next-refresh", user: next }); return true; }
    if (path.endsWith("/me/") && loggedIn) { await json(next); return true; }
    if (path.endsWith("/profile") && !loggedIn) { pending = true; await gate.promise; await json({ detail: "old session rejected" }, 401); return true; }
    if (path.endsWith("/profile") && loggedIn) { await json({ user_id: "456", version: 0, additional_info: {} }); return true; }
    return false;
  });
  await page.goto("/profile");
  await expect.poll(() => pending).toBe(true);
  await page.locator(".sidebar-account").click();
  await page.getByRole("menuitem", { name: "Cerrar sesion" }).click();
  await page.getByLabel("Usuario", { exact: true }).fill(next.username);
  await page.getByLabel("Password", { exact: true }).fill("synthetic-password");
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page.locator(".sidebar-account")).toContainText(next.username);
  gate.release();
  await expect.poll(async () => page.evaluate(() => JSON.parse(localStorage.getItem("blandskron.auth"))?.user?.id)).toBe(456);
  await page.locator(".sidebar-account").click();
  await expect(page.getByRole("menuitem", { name: "Cerrar sesion" })).toBeVisible();
  expect(errors).toEqual([]);
});

test("admin refuses duplicate submit, preserves conflicts and resets forms across tenants", async ({ page }) => {
  const gate = latch(); let writes = 0;
  const errors = await prepare(page, person(123, true), async (route, path, json) => {
    if (path.endsWith("/tenant-areas/") && route.request().method() === "POST") {
      writes++; await gate.promise; await json({ detail: "Recarga las relaciones de la empresa." }, 409); return true;
    }
    return false;
  });
  await page.goto("/admin");
  const name = page.getByLabel("Nombre del area", { exact: true });
  await name.fill("Borrador sintético");
  await name.evaluate((input) => { input.form.requestSubmit(); input.form.requestSubmit(); });
  await expect.poll(() => writes).toBe(1);
  await expect(page.getByLabel("Empresa activa")).toBeDisabled();
  gate.release();
  await expect(page.getByRole("alert")).toContainText("Recarga las relaciones");
  await expect(name).toHaveValue("Borrador sintético");
  await page.getByLabel("Empresa activa").selectOption("tenant-two");
  await expect(name).toHaveValue("");
  expect(errors).toEqual([]);
});
