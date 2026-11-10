import AxeBuilder from "@axe-core/playwright";
import { test, expect } from "@playwright/test";
import { normalizeAuthUser } from "../../src/entities/auth/model/auth.user.ts";

const identity = {
  id: 123,
  username: "demo",
  display_name: "Usuario de prueba",
  is_superuser: true,
  active_tenant_id: "tenant-demo",
  active_role: "TENANT_ADMIN",
  active_permissions: ["*"],
  tenant_memberships: [
    {
      tenant_id: "tenant-demo",
      tenant_name: "Empresa de prueba",
      role: "TENANT_ADMIN",
      permissions: ["*"],
    },
  ],
};
const sampleDocument = {
  document_id: "document-demo",
  filename: "Contrato de prueba.pdf",
  mime_type: "application/pdf",
  status: "PROCESSED",
  chunk_count: 4,
  updated_at: "2026-11-10T12:00:00Z",
};

async function prepare(page, { authenticated = true, theme = "light" } = {}) {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.addInitScript(
    ({ user, raw, authenticated, theme }) => {
      const names = [
        "AUTH",
        "PROFILE",
        "RAG_CHAT",
        "RAG_DOCUMENT",
        "DOCUMENT_SEARCH",
        "DOCUMENT_ACCESS",
        "DOCUMENT_LIBRARY",
        "DOCUMENT_TRANSFER",
        "DOCUMENT_EXPORT",
        "GOOGLE_DRIVE_IMPORT",
        "CONVERSATION",
      ];
      window.__BLANDSKRON_CONFIG__ = Object.fromEntries(
        names.map((name) => [
          `VITE_${name}_BASE_URL`,
          `${location.origin}/test-api`,
        ]),
      );
      localStorage.setItem("blandskron:theme", theme);
      if (authenticated)
        localStorage.setItem(
          "blandskron.auth",
          JSON.stringify({
            user,
            access: `synthetic.${btoa(JSON.stringify(raw))}.synthetic`,
            refresh: "synthetic-refresh",
            username: "demo",
            sessionId: "11111111-1111-1111-1111-111111111111",
          }),
        );
    },
    { user: normalizeAuthUser(identity), raw: identity, authenticated, theme },
  );
  let folders = [];
  await page.route("**/test-api/**", async (route) => {
    const url = new URL(route.request().url()),
      path = url.pathname,
      method = route.request().method();
    const json = (body) => route.fulfill({ json: body });
    const pageOf = (items) => ({
      items,
      limit: 50,
      offset: 0,
      has_more: false,
    });
    if (path.endsWith("/me/")) return json(identity);
    if (path.endsWith("/logout/")) return json({});
    if (path.endsWith("/profile"))
      return json({
        profile_id: "profile-demo",
        user_id: "123",
        version: 1,
        email: "demo@example.com",
        phone_number: null,
        profile_picture_url: null,
        additional_info: { full_name: "Usuario de prueba" },
      });
    if (path.endsWith("/documents/search"))
      return json({ items: [sampleDocument], total: 1, limit: 20, offset: 0 });
    if (path.endsWith("/library/recent")) return json(pageOf([sampleDocument]));
    if (path.endsWith("/library/favorites")) return json(pageOf([]));
    if (path.endsWith("/library/markers"))
      return json([
        { document_id: sampleDocument.document_id, is_favorite: false },
      ]);
    if (path.endsWith("/folders") && method === "POST") {
      const body = route.request().postDataJSON();
      const folder = {
        folder_id: "folder-demo",
        name: body.name,
        document_count: 0,
      };
      folders.push(folder);
      return json(folder);
    }
    if (path.endsWith("/folders")) return json(pageOf(folders));
    if (path.includes("/folders/") && path.endsWith("/documents"))
      return json(pageOf([]));
    if (path.endsWith("/transfers")) return json(pageOf([]));
    if (
      ["assigned-to-me", "managed-by-me", "notifications"].some((name) =>
        path.endsWith(`/documents/${name}`),
      )
    )
      return json(pageOf([]));
    if (path.endsWith("/google-drive/connection"))
      return json({ connected: false, enabled: false, version: 0 });
    if (path.endsWith("/conversations"))
      return json(
        method === "GET"
          ? [
              {
                conversation_id: "conversation-demo",
                title: "Consulta documental",
              },
            ]
          : {
              conversation_id: "conversation-demo",
              title: "Consulta documental",
            },
      );
    if (path.endsWith("/messages")) return json([]);
    if (path.includes("/conversations/") && path.endsWith("/documents"))
      return json({ document_ids: [] });
    if (path.endsWith("/tenants/"))
      return json([
        {
          tenant_id: "tenant-demo",
          name: "Empresa de prueba",
          status: "ACTIVE",
        },
      ]);
    if (
      [
        "crud/",
        "tenant-areas/",
        "tenant-memberships/",
        "tenant-groups/",
        "tenant-user-groups/",
      ].some((name) => path.endsWith(`/${name}`))
    )
      return json([]);
    throw new Error(`Fixture missing: ${method} ${path}`);
  });
  return errors;
}

async function checkAccessibility(page) {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(
    result.violations.map(({ id, nodes }) => ({
      id,
      targets: nodes.map((node) => node.target),
    })),
  ).toEqual([]);
}

test("login has clear labels, keyboard focus and accessible contrast", async ({
  page,
}, info) => {
  const errors = await prepare(page, { authenticated: false });
  await page.goto("/login");
  await expect(
    page.getByRole("heading", { level: 1, name: "Bienvenido de nuevo" }),
  ).toBeVisible();
  await page.getByLabel("Usuario", { exact: true }).focus();
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Contraseña", { exact: true })).toBeFocused();
  await checkAccessibility(page);
  await page.screenshot({ path: info.outputPath("login-light.png") });
  expect(errors).toEqual([]);
});

for (const theme of ["light", "dark"])
  test(`chat suggestions work and ${theme} theme is accessible`, async ({
    page,
  }, info) => {
    const errors = await prepare(page, { theme });
    await page.goto("/");
    await expect(
      page.getByRole("heading", {
        name: "Tus documentos, con respuestas claras",
      }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Resumir un documento" }).click();
    await expect(
      page.getByRole("textbox", { name: "Pregunta documental" }),
    ).toHaveValue("Resume los puntos principales de mis documentos.");
    await expect(
      page.locator("button button, button [role=button]"),
    ).toHaveCount(0);
    await checkAccessibility(page);
    await page.screenshot({ path: info.outputPath(`chat-${theme}.png`) });
    expect(errors).toEqual([]);
  });

test("library has working layouts, disclosure keyboard handling and folder dialog", async ({
  page,
}, info) => {
  const errors = await prepare(page);
  await page.goto("/documents");
  await expect(
    page.getByRole("heading", { name: sampleDocument.filename }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Vista lista", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Vista lista", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  const actions = page.getByRole("button", {
    name: `Acciones de ${sampleDocument.filename}`,
  });
  await actions.click();
  await page.getByRole("button", { name: "Descargar", exact: true }).focus();
  await page.keyboard.press("Escape");
  await expect(actions).toBeFocused();
  await expect(actions).toHaveAttribute("aria-expanded", "false");
  await page
    .getByRole("button", { name: "Vista cuadrícula", exact: true })
    .click();
  await checkAccessibility(page);
  await page.screenshot({ path: info.outputPath("library-light.png") });
  const create = page.getByRole("button", {
    name: "Nueva Carpeta",
    exact: true,
  });
  await create.click();
  const dialog = page.getByRole("dialog", { name: "Nueva Carpeta" });
  await expect(
    dialog.getByRole("textbox", { name: "Nombre de carpeta" }),
  ).toBeFocused();
  await checkAccessibility(page);
  await dialog
    .getByRole("textbox", { name: "Nombre de carpeta" })
    .fill("Carpeta sintética");
  await dialog.getByRole("button", { name: "Crear", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  await expect(create).toBeFocused();
  await page.getByRole("button", { name: "Carpetas", exact: true }).click();
  await expect(
    page.getByRole("button", { name: /Carpeta sintética/ }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

for (const width of [320, 390])
  test(`mobile navigation traps focus, closes and preserves content at ${width}px`, async ({
    page,
  }, info) => {
    await page.setViewportSize({ width, height: 844 });
    const errors = await prepare(page, {
      theme: width === 390 ? "dark" : "light",
    });
    await page.goto("/documents");
    await expect(
      page.getByRole("heading", { name: sampleDocument.filename }),
    ).toBeVisible();
    const trigger = page.getByRole("button", {
      name: "Abrir navegación",
      exact: true,
    });
    await trigger.click();
    const drawer = page.getByRole("dialog", {
      name: "Navegación principal",
      exact: true,
    });
    await expect(drawer).toBeVisible();
    for (let index = 0; index < 16; index++) await page.keyboard.press("Tab");
    await expect
      .poll(() =>
        page.evaluate(() =>
          document
            .querySelector("dialog[open]")
            .contains(document.activeElement),
        ),
      )
      .toBe(true);
    await checkAccessibility(page);
    await page.keyboard.press("Escape");
    await expect(trigger).toBeFocused();
    await expect(drawer).not.toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await checkAccessibility(page);
    await page.screenshot({
      path: info.outputPath(`library-mobile-${width}.png`),
    });
    await trigger.click();
    await drawer
      .getByRole("button", { name: "Aplicaciones", exact: true })
      .click();
    await expect(page).toHaveURL(/\/applications$/);
    await expect(drawer).not.toBeVisible();
    await page.goBack();
    await expect(page).toHaveURL(/\/documents$/);
    expect(errors).toEqual([]);
  });

test("a failed page chunk offers recovery without exposing technical errors", async ({
  page,
}) => {
  await prepare(page);
  await page.route("**/ProfilePage-*.js", (route) => route.abort());
  await page.goto("/profile");
  await expect(
    page.getByRole("heading", { name: "No pudimos mostrar esta página" }),
  ).toBeVisible();
  await page.unroute("**/ProfilePage-*.js");
  await page
    .getByRole("button", { name: "Volver a cargar", exact: true })
    .click();
  await expect(page.getByLabel("Nombre Completo")).toHaveValue(
    "Usuario de prueba",
  );
});

test("duplicate folder submissions create one folder", async ({ page }) => {
  await prepare(page);
  let writes = 0;
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      new URL(request.url()).pathname.endsWith("/folders")
    )
      writes++;
  });
  await page.goto("/documents");
  await page
    .getByRole("button", { name: "Nueva Carpeta", exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Nueva Carpeta",
    exact: true,
  });
  await dialog.getByLabel("Nombre de carpeta").fill("Una sola carpeta");
  await dialog.locator("form").evaluate((form) => {
    form.requestSubmit();
    form.requestSubmit();
  });
  await expect(dialog).not.toBeVisible();
  expect(writes).toBe(1);
});

for (const theme of ["light", "dark"])
  for (const route of ["/profile", "/admin", "/applications"])
    test(`${route} keeps its landmarks and accessible controls in ${theme}`, async ({
      page,
    }) => {
      const errors = await prepare(page, { theme });
      await page.goto(route);
      await expect(page.locator("main")).toBeVisible();
      if (route === "/profile")
        await expect(page.getByLabel("Nombre Completo")).toHaveValue(
          "Usuario de prueba",
        );
      if (route === "/admin")
        await expect(
          page.getByRole("combobox", { name: "Empresa activa", exact: true }),
        ).toBeVisible();
      await checkAccessibility(page);
      expect(errors).toEqual([]);
    });
