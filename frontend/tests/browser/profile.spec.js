import { test, expect } from "@playwright/test";

const identity = { id: 123, username: "synthetic", email: "identity@example.com", display_name: "Persona sintética",
  is_staff: true, active_tenant_id: "tenant-one", active_role: "USER", active_permissions: ["use_chat"],
  tenant_memberships: [{ tenant_id: "tenant-other", tenant_name: "Otro tenant", role: "TENANT_ADMIN", groups: ["Oculto"] },
    { tenant_id: "tenant-one", tenant_name: "Tenant sintético", role: "USER", groups: ["Lectura"] }] };
const access = (id) => `synthetic.${Buffer.from(JSON.stringify({ ...identity, jti: id })).toString("base64url")}.synthetic`;
const initial = () => ({ profile_id: "synthetic-profile", user_id: "123", version: 1, email: "contact@example.com",
  phone_number: null, profile_picture_url: null, additional_info: { full_name: "Nombre guardado" }, groups: [], permissions: [] });

async function prepare(page, respond) {
  await page.addInitScript(({ token, user }) => {
    window.__BLANDSKRON_CONFIG__ = Object.fromEntries(["AUTH", "PROFILE", "RAG_CHAT", "RAG_DOCUMENT", "DOCUMENT_SEARCH",
      "DOCUMENT_ACCESS", "DOCUMENT_LIBRARY", "DOCUMENT_TRANSFER", "DOCUMENT_EXPORT", "GOOGLE_DRIVE_IMPORT", "CONVERSATION"]
      .map((key) => [`VITE_${key}_BASE_URL`, `${location.origin}/test-api`]));
    localStorage.setItem("blandskron.auth", JSON.stringify({ access: token, refresh: "synthetic-refresh", username: "synthetic",
      user: { id: user.id, username: user.username, email: user.email, displayName: user.display_name, isStaff: true,
        activeTenantId: "tenant-one", activeTenantRole: "USER", permissions: ["use_chat"], tenantMemberships: user.tenant_memberships } }));
  }, { token: access("first"), user: identity });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/test-api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = (body, status = 200) => route.fulfill({ status, json: body });
    if (path.endsWith("/api/users/me/")) return json(identity);
    if (path.endsWith("/api/users/token/refresh/")) return json({ access: access("renewed") });
    if (path.endsWith("/api/users/logout/")) return json({});
    if (await respond(route, path, json)) return;
    throw new Error(`Unexpected fixture request: ${path}`);
  });
  await page.goto("/profile");
  await expect(page.getByLabel("Nombre Completo")).toHaveValue("Nombre guardado");
  return errors;
}

test("refresh during avatar upload preserves the contact draft and serializes writes", async ({ page }) => {
  let profile = initial(), uploads = 0, writes = 0;
  const readTokens = [];
  const errors = await prepare(page, async (route, path, json) => {
    if (path.endsWith("/api/v1/profile")) {
      if (route.request().method() === "PUT") {
        writes++;
        const body = route.request().postDataJSON();
        expect(body.expected_version).toBe(2);
        expect(body.additional_info.full_name).toBe("Borrador sin guardar");
        profile = { ...profile, ...body, version: 3 };
      } else readTokens.push(route.request().headers().authorization);
      await json(profile); return true;
    }
    if (path.endsWith("/api/v1/profile/upload")) {
      uploads++;
      if (uploads === 1) await json({ detail: "expired" }, 401);
      else { profile = { ...profile, version: 2 }; await json(profile); }
      return true;
    }
  });
  await page.getByLabel("Nombre Completo").fill("Borrador sin guardar");
  await page.locator('input[type="file"]').setInputFiles({ name: "synthetic.png", mimeType: "image/png", buffer: Buffer.from("synthetic") });
  await expect.poll(() => uploads).toBe(2);
  await expect(page.getByRole("button", { name: "Guardar cambios", exact: true })).toBeEnabled();
  await expect(page.getByLabel("Nombre Completo")).toHaveValue("Borrador sin guardar");
  expect(readTokens).not.toContain(`Bearer ${access("renewed")}`);
  await page.locator("form.profile-form").evaluate((form) => { form.requestSubmit(); form.requestSubmit(); });
  await expect(page.getByRole("status")).toContainText("actualizado correctamente");
  expect(writes).toBe(1);
  expect(errors).toEqual([]);
});

test("conflicts preserve edits, reload is explicit and contact email is independent", async ({ page }) => {
  let profile = initial(), writes = 0;
  const errors = await prepare(page, async (route, path, json) => {
    if (!path.endsWith("/api/v1/profile")) return false;
    if (route.request().method() === "GET") await json(profile);
    else { writes++; profile = { ...profile, version: 2, additional_info: { full_name: "Otra sesión" } }; await json({ detail: "conflict" }, 409); }
    return true;
  });
  await expect(page.getByLabel("Correo de contacto")).toBeEditable();
  await expect(page.getByText("No cambia tu usuario ni el correo de identidad:", { exact: false })).toContainText(identity.email);
  await page.getByLabel("Nombre Completo").fill("Mi borrador");
  await page.getByRole("button", { name: "Guardar cambios", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("otra sesión");
  await expect(page.getByLabel("Nombre Completo")).toHaveValue("Mi borrador");
  await page.getByRole("button", { name: "Descartar cambios y recargar perfil" }).click();
  await expect(page.getByLabel("Nombre Completo")).toHaveValue("Otra sesión");
  expect(writes).toBe(1); expect(errors).toEqual([]);
});

test("permissions reflect only the active tenant; invalid uploads remain local", async ({ page }) => {
  let uploads = 0;
  const errors = await prepare(page, async (route, path, json) => {
    if (path.endsWith("/api/v1/profile")) { await json(initial()); return true; }
    if (path.endsWith("/profile/upload")) { uploads++; await json(initial()); return true; }
  });
  await expect(page.getByLabel("Nombre Completo")).toHaveAttribute("maxlength", "120");
  await expect(page.getByLabel("Biografía / Acerca de mí")).toHaveAttribute("maxlength", "2000");
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Subir nueva imagen" }).focus();
  await page.keyboard.press("Enter");
  await (await chooser).setFiles({ name: "synthetic.gif", mimeType: "image/gif", buffer: Buffer.from("synthetic") });
  await expect(page.getByRole("alert")).toContainText("imagen válido");
  await page.locator('input[type="file"]').setInputFiles({ name: "synthetic.png", mimeType: "image/png", buffer: Buffer.alloc(5 * 1024 * 1024 + 1) });
  await expect(page.getByRole("alert")).toContainText("límite"); expect(uploads).toBe(0);
  await page.getByRole("button", { name: "Permisos y Accesos", exact: true }).click();
  const panel = page.getByRole("region", { name: "Permisos efectivos de la sesión" });
  await expect(panel).toContainText("Tenant sintético"); await expect(panel).toContainText("use_chat");
  await expect(panel).not.toContainText("TENANT_ADMIN"); await expect(panel).not.toContainText("Oculto");
  await expect(page.getByRole("button", { name: "Permisos y Accesos", exact: true })).toHaveAttribute("aria-pressed", "true");
  expect(errors).toEqual([]);
});
