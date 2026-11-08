import { test, expect } from "@playwright/test";

const identity = { id: 123, username: "synthetic", email: "identity@example.com", display_name: "Persona sintética",
  active_tenant_id: "tenant-one", active_role: "USER", active_permissions: ["use_chat"],
  tenant_memberships: [{ tenant_id: "tenant-one", tenant_name: "Tenant sintético", role: "USER", groups: [] }] };
const access = (id) => `synthetic.${Buffer.from(JSON.stringify({ ...identity, jti: id })).toString("base64url")}.synthetic`;
const row = (id, status = "COMPLETED") => ({ export_id: id, title: "Documento " + id, filename: `${id}.pdf`,
  status, file_size_bytes: 128, mime_type: "application/pdf", metadata: {} });

async function prepare(page, respond) {
  await page.addInitScript(({ token, user }) => {
    window.__BLANDSKRON_CONFIG__ = Object.fromEntries(["AUTH", "PROFILE", "RAG_CHAT", "RAG_DOCUMENT", "DOCUMENT_SEARCH",
      "DOCUMENT_ACCESS", "DOCUMENT_LIBRARY", "DOCUMENT_TRANSFER", "DOCUMENT_EXPORT", "GOOGLE_DRIVE_IMPORT", "CONVERSATION"]
      .map((key) => [`VITE_${key}_BASE_URL`, `${location.origin}/test-api`]));
    localStorage.setItem("blandskron.auth", JSON.stringify({ access: token, refresh: "synthetic-refresh", username: "synthetic",
      user: { id: user.id, username: user.username, displayName: user.display_name, activeTenantId: "tenant-one",
        activeTenantRole: "USER", permissions: ["use_chat"], tenantMemberships: user.tenant_memberships } }));
  }, { token: access("first"), user: identity });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/test-api/**", async (route) => {
    const url = new URL(route.request().url()), path = url.pathname;
    const json = (body, status = 200) => route.fulfill({ status, json: body });
    if (path.endsWith("/api/users/me/")) return json(identity);
    if (path.endsWith("/api/users/token/refresh/")) return json({ access: access("renewed") });
    if (path.endsWith("/api/v1/profile")) return json({ user_id: "123", profile_id: null, version: 0, additional_info: {} });
    if (path.endsWith("/api/v1/transfers")) return json({ items: [], limit: 50, offset: 0, has_more: false });
    if (path.endsWith("/api/v1/conversations")) return json([{ conversation_id: "remote-chat", title: "Chat sintético" }]);
    if (path.endsWith("/api/v1/conversations/remote-chat/messages")) return json([{ message_id: "remote-message", role: "assistant", content: "Respuesta sintética", sources: [] }]);
    if (path.endsWith("/api/v1/conversations/remote-chat/documents")) return json({ document_ids: [] });
    if (await respond(route, path, json, url)) return;
    throw new Error(`Unexpected fixture request: ${path}`);
  });
  await page.goto("/chat");
  await expect(page.getByText("Respuesta sintética", { exact: true })).toBeVisible();
  return errors;
}

test("PDF history paginates, exposes status, deletes and restores keyboard focus", async ({ page }) => {
  let removed = false;
  const errors = await prepare(page, async (route, path, json, url) => {
    if (path.endsWith("/api/v1/exports/one") && route.request().method() === "DELETE") { removed = true; await json({ deleted: true }); return true; }
    if (path.endsWith("/api/v1/exports")) {
      expect(url.searchParams.get("limit")).toBe("20");
      await json(removed ? { items: [], next_cursor: null } : url.searchParams.has("before")
        ? { items: [row("two", "EXPIRED"), row("three", "MIGRATION_REQUIRED")], next_cursor: null }
        : { items: [row("one")], next_cursor: "next" }); return true;
    }
  });
  const trigger = page.getByRole("button", { name: "Mis PDFs", exact: true });
  await trigger.click(); const dialog = page.getByRole("dialog", { name: "Mis PDFs" });
  await expect(dialog.getByText("Documento one", { exact: true })).toBeVisible();
  await dialog.getByRole("button", { name: "Cargar más PDFs" }).click();
  await expect(dialog.getByText("3 PDFs cargados")).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Descargar Documento two" })).toBeDisabled();
  await expect(dialog.getByText(/Requiere revisión/)).toBeVisible();
  if (process.env.EXPORT_QA_SCREENSHOT) await page.screenshot({ path: process.env.EXPORT_QA_SCREENSHOT });
  await dialog.getByRole("button", { name: "Eliminar Documento one" }).click();
  await expect(dialog.getByText("No hay PDFs guardados.")).toBeVisible();
  await page.keyboard.press("Escape"); await expect(dialog).not.toBeVisible(); await expect(trigger).toBeFocused();
  expect(errors).toEqual([]);
});

test("expired download stays visible and cancel suppresses late PDF download", async ({ page }) => {
  let release, reached;
  const waiting = new Promise((resolve) => { reached = resolve; });
  const gate = new Promise((resolve) => { release = resolve; });
  let downloads = 0;
  page.on("download", () => downloads++);
  const errors = await prepare(page, async (route, path, json) => {
    if (path.endsWith("/api/v1/exports")) { await json({ items: [row("one"), row("slow")], next_cursor: null }); return true; }
    if (path.endsWith("/api/v1/exports/one/download")) { await json({ detail: "expired" }, 410); return true; }
    if (path.endsWith("/api/v1/exports/slow/download")) {
      reached(); await gate;
      try { await route.fulfill({ contentType: "application/pdf", body: "%PDF-synthetic" }); } catch { /* Request was aborted by user. */ }
      return true;
    }
  });
  await page.getByRole("button", { name: "Mis PDFs", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Mis PDFs" });
  await dialog.getByRole("button", { name: "Descargar Documento one" }).click();
  await expect(dialog.getByRole("alert")).toContainText("expiró");
  await dialog.getByRole("button", { name: "Descargar Documento slow" }).click(); await waiting;
  await dialog.getByRole("button", { name: "Cancelar operación PDF" }).click(); release();
  await expect(dialog.getByRole("button", { name: "Descargar Documento slow" })).toBeEnabled();
  expect(downloads).toBe(0); expect(errors).toEqual([]);
});

test("refresh during PDF creation retains operation and valid blob downloads once", async ({ page }) => {
  const keys = [], tokens = [];
  const errors = await prepare(page, async (route, path, json) => {
    if (path.endsWith("/api/v1/exports/chat-message/pdf")) {
      keys.push(route.request().headers()["idempotency-key"]);
      tokens.push(route.request().headers().authorization);
      await json(keys.length === 1 ? { detail: "expired" } : row("created"), keys.length === 1 ? 401 : 200); return true;
    }
    if (path.endsWith("/api/v1/exports/created/download")) {
      await route.fulfill({ contentType: "application/pdf", body: "%PDF-synthetic" }); return true;
    }
  });
  const download = page.waitForEvent("download");
  await page.getByTitle("Exportar respuesta como PDF").click();
  expect((await download).suggestedFilename()).toBe("created.pdf");
  expect(keys).toHaveLength(2); expect(keys[0]).toBeTruthy(); expect(keys[0]).toBe(keys[1]);
  expect(tokens[0]).not.toBe(tokens[1]); expect(errors).toEqual([]);
});
