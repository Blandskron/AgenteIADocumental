import { test, expect } from "@playwright/test";

const sessionId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const user = { id: 123, username: "synthetic", active_tenant_id: "tenant-one", active_role: "USER",
  active_permissions: ["use_google_drive", "upload_documents"], tenant_memberships: [] };
const access = (jti) => `synthetic.${Buffer.from(JSON.stringify({ ...user, jti })).toString("base64url")}.synthetic`;

async function prepare(page, { attempt = true, wrongScope = false, refresh = false, importMode = null } = {}) {
  await page.addInitScript(({ user, token, sessionId, attempt, wrongScope }) => {
    window.__BLANDSKRON_CONFIG__ = Object.fromEntries(["AUTH", "PROFILE", "RAG_CHAT", "RAG_DOCUMENT", "DOCUMENT_SEARCH",
      "DOCUMENT_ACCESS", "DOCUMENT_LIBRARY", "DOCUMENT_TRANSFER", "DOCUMENT_EXPORT", "GOOGLE_DRIVE_IMPORT", "CONVERSATION"]
      .map((key) => [`VITE_${key}_BASE_URL`, `${location.origin}/test-api`]));
    if (!localStorage.getItem("blandskron.auth")) localStorage.setItem("blandskron.auth", JSON.stringify({
      sessionId, access: token, refresh: "synthetic-refresh", username: "synthetic",
      user: { id: user.id, username: user.username, activeTenantId: "tenant-one", activeTenantRole: "USER",
        permissions: user.active_permissions, tenantMemberships: [] },
    }));
    if (attempt) sessionStorage.setItem("blandskron.drive.oauth.v1", JSON.stringify({
      scope: JSON.stringify([sessionId, user.id, wrongScope ? "another-tenant" : "tenant-one"]), state: "s".repeat(43),
      verifier: "v".repeat(43), createdAt: Date.now(), callbackPath: location.pathname,
    }));
  }, { user, token: access("first"), sessionId, attempt, wrongScope });
  const calls = [], errors = [], imports = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/test-api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = (body, status = 200) => route.fulfill({ status, json: body });
    if (path.endsWith("/api/users/me/")) return json(user);
    if (path.endsWith("/api/users/token/refresh/")) return json({ access: access("renewed"), user });
    if (path.endsWith("/api/v1/profile")) return json({ user_id: "123", version: 0, additional_info: {} });
    if (path.endsWith("/google-drive/oauth/callback")) {
      calls.push(route.request().postDataJSON());
      if (refresh && calls.length === 1) return json({ detail: "expired" }, 401);
      return json({ connected: true, enabled: true, version: 2, grant_status: "ACTIVE",
        provider_account_id: "synthetic", provider_account_email: "synthetic@example.invalid" });
    }
    if (path.endsWith("/google-drive/connection")) return json({ connected: true, enabled: true, version: 2,
      grant_status: "ACTIVE", provider_account_email: "synthetic@example.invalid" });
    if (path.endsWith("/google-drive/disconnect")) return json({ connected: false, enabled: true, version: 3, grant_status: "DISCONNECTED" });
    if (path.endsWith("/google-drive/imports") && route.request().method() === "POST" && importMode) {
      imports.push(route.request().postDataJSON());
      if (importMode === "lost" && imports.length === 1) return route.abort("failed");
      return json({ import_id: "synthetic-import", operation_id: imports.at(-1).operation_id, version: 2,
        status: importMode === "ambiguous" ? "REVIEW_REQUIRED" : "COMPLETED", files: [] });
    }
    if (/document-library|\/folders|\/favorites|\/recent/.test(path)) return json({ items: [], limit: 50, offset: 0, has_more: false });
    if (/\/search/.test(path)) return json({ documents: [], total: 0 });
    if (path.endsWith("/api/v1/conversations")) return json([{ conversation_id: "synthetic-chat", title: "Chat sintético" }]);
    return json([]);
  });
  return { calls, errors, imports };
}

for (const path of ["/applications/google-drive", "/documents"]) {
  test(`lost import response on ${path} reuses its operation after reload`, async ({ page }) => {
    const { imports, errors } = await prepare(page, { attempt: false, importMode: "lost" });
    await page.goto(path);
    if (path === "/documents") await page.getByRole("button", { name: "Google Drive", exact: true }).click();
    await page.getByRole("textbox", { name: /IDs de archivos de Google Drive/ }).fill("synthetic-file");
    await page.locator("form").filter({ has: page.getByRole("textbox", { name: /IDs de archivos de Google Drive/ }) }).locator('button[type="submit"]').click();
    await expect.poll(() => imports.length).toBe(1);
    await expect(page.getByRole("button", { name: "Consultar importación pendiente" })).toBeEnabled();
    await page.reload();
    if (path === "/documents") await page.getByRole("button", { name: "Google Drive", exact: true }).click();
    await page.getByRole("button", { name: "Consultar importación pendiente" }).click();
    await expect.poll(() => imports.length).toBe(2);
    expect(imports[1]).toEqual(imports[0]);
    await expect(page.getByRole("button", { name: "Consultar importación pendiente" })).not.toBeVisible();
    expect(errors).toEqual([]);
  });
}

for (const path of ["/applications/google-drive", "/documents"]) {
  test(`Drive callback on ${path} survives access refresh and disconnects explicitly`, async ({ page }) => {
    const { calls, errors } = await prepare(page, { refresh: true });
    await page.goto(`${path}?code=synthetic-code&state=${"s".repeat(43)}&iss=https%3A%2F%2Faccounts.google.com`);
    await expect.poll(() => calls.length).toBe(2); // 401 before exchange, one retry after session refresh.
    expect(calls[0]).toEqual(calls[1]);
    await expect(page).toHaveURL(new RegExp(`${path}$`));
    if (path === "/documents") await page.getByRole("button", { name: /Google Drive/ }).first().click();
    const disconnect = page.getByRole("button", { name: "Desconectar Google Drive", exact: true });
    await expect(disconnect).toBeVisible();
    await disconnect.click();
    await expect(disconnect).not.toBeVisible();
    expect(errors).toEqual([]);
  });

  test(`Drive rejects unsolicited or different-tenant callback on ${path}`, async ({ page }) => {
    const { calls, errors } = await prepare(page, { wrongScope: true });
    await page.goto(`${path}?code=synthetic-code&state=${"s".repeat(43)}&error_description=private`);
    await expect(page).toHaveURL(new RegExp(`${path}$`));
    await expect(page.getByText(/autorización de Drive no corresponde/)).toBeVisible();
    expect(calls).toEqual([]);
    expect(errors).toEqual([]);
  });
}

for (const path of ["/applications/google-drive", "/documents"]) {
  test(`Drive history on ${path} pages, reviews partial files and restores keyboard focus`, async ({ page }) => {
    const { errors } = await prepare(page, { attempt: false });
    await page.route("**/test-api/**/google-drive/imports**", async (route) => {
      const url = new URL(route.request().url());
      const row = (id) => ({ import_id: id, status: "REVIEW_REQUIRED", created_at: "2026-01-01T00:00:00Z", total_files: 2, processed_files: 1 });
      if (url.pathname.endsWith("/files")) return route.fulfill({ json: { items: [{ import_file_id: "file-one", import_id: "one", filename: "sintetico.txt", status: "COMPLETED", document_id: "saved-document",
        metadata: { folder_association: { status: "FAILED" }, document_status: "REVIEW_REQUIRED" } }], next_cursor: null } });
      if (url.pathname.endsWith("/one")) return route.fulfill({ json: row("one") });
      return route.fulfill({ json: { items: [row(url.searchParams.has("before") ? "two" : "one")], next_cursor: url.searchParams.has("before") ? null : "next" } });
    });
    await page.goto(path);
    if (path === "/documents") await page.getByRole("button", { name: "Google Drive", exact: true }).click();
    const opener = page.getByRole("button", { name: "Historial de Drive", exact: true });
    await opener.click();
    const dialog = page.getByRole("dialog", { name: "Historial de Drive", exact: true });
    await expect(dialog.getByText("1 importaciones cargadas", { exact: true })).toBeVisible();
    await dialog.getByRole("button", { name: "Cargar más importaciones" }).click();
    await expect(dialog.getByText("2 importaciones cargadas", { exact: true })).toBeVisible();
    await expect(dialog.getByRole("button", { name: "Cargar más importaciones" })).not.toBeVisible();
    await dialog.getByRole("button", { name: /REVIEW_REQUIRED/ }).first().click();
    await expect(dialog.getByText(/Documento: saved-document/)).toBeVisible();
    await expect(dialog.getByText(/documento se conservó/)).toBeVisible();
    await expect(dialog.getByText(/Resultado incierto/)).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(dialog).not.toBeVisible();
    await expect(opener).toBeFocused();
    expect(errors).toEqual([]);
  });
  test(`Drive cancellation on ${path} retains the operation and ignores its late response`, async ({ page }) => {
    const { errors } = await prepare(page, { attempt: false });
    const bodies = []; let release;
    const held = new Promise((resolve) => { release = resolve; });
    await page.route("**/test-api/**/google-drive/imports", async (route) => {
      if (route.request().method() !== "POST") return route.fulfill({ json: { items: [], next_cursor: null } });
      bodies.push(route.request().postDataJSON());
      if (bodies.length === 1) await held;
      await route.fulfill({ json: { import_id: "saved", status: "COMPLETED", files: [] } }).catch(() => {});
    });
    await page.goto(path);
    if (path === "/documents") await page.getByRole("button", { name: "Google Drive", exact: true }).click();
    await page.getByRole("textbox", { name: /IDs de archivos de Google Drive/ }).fill("synthetic-file");
    await page.locator("form").filter({ has: page.getByRole("textbox", { name: /IDs de archivos de Google Drive/ }) }).locator('button[type="submit"]').click();
    await expect.poll(() => bodies.length).toBe(1);
    await page.getByRole("button", { name: "Dejar de esperar", exact: true }).click();
    release();
    await expect(page.getByRole("button", { name: "Consultar importación pendiente" })).toBeEnabled();
    await page.getByRole("button", { name: "Consultar importación pendiente" }).click();
    await expect.poll(() => bodies.length).toBe(2);
    expect(bodies[1]).toEqual(bodies[0]);
    expect(errors).toEqual([]);
  });
}
