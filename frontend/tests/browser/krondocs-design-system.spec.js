import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { normalizeAuthUser } from "../../src/entities/auth/model/auth.user.ts";

const identity = {
  id: 123,
  username: "ana.martinez",
  display_name: "Ana Martínez",
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

async function setupKronDocsMocks(page, { theme = null } = {}) {
  const errors = [];
  page.on("pageerror", (err) => errors.push(err.message));

  await page.addInitScript(
    ({ user, raw, initialTheme }) => {
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
        "KNOWLEDGE_STUDIO",
        "AGENT_ORCHESTRATOR",
      ];
      window.__BLANDSKRON_CONFIG__ = Object.fromEntries(
        names.map((name) => [
          `VITE_${name}_BASE_URL`,
          `${location.origin}/test-api`,
        ]),
      );
      if (initialTheme) {
        localStorage.setItem("krondocs:theme", initialTheme);
      } else {
        localStorage.removeItem("krondocs:theme");
        localStorage.removeItem("blandskron:theme");
      }
      localStorage.setItem(
        "blandskron.auth",
        JSON.stringify({
          user,
          access: `synthetic.${btoa(JSON.stringify(raw))}.synthetic`,
          refresh: "synthetic-refresh",
          username: "ana.martinez",
          sessionId: "11111111-1111-1111-1111-111111111111",
        }),
      );
    },
    { user: normalizeAuthUser(identity), raw: identity, initialTheme: theme },
  );

  await page.route("**/test-api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = (body) => route.fulfill({ json: body });
    const pageOf = (items) => ({
      items,
      limit: 50,
      offset: 0,
      has_more: false,
    });
    if (path.endsWith("/me/")) return json(identity);
    if (path.endsWith("/profile"))
      return json({
        profile_id: "profile-demo",
        user_id: "123",
        version: 1,
        email: "ana@example.com",
        phone_number: null,
        profile_picture_url: null,
        additional_info: { full_name: "Ana Martínez" },
      });
    if (path.endsWith("/conversations")) {
      return json([
        {
          conversation_id: "conv-1",
          title: "Consulta normativa",
        },
      ]);
    }
    if (path.endsWith("/messages")) {
      return json([
        {
          message_id: "m-1",
          role: "user",
          content: "¿Cuál es la vigencia?",
        },
        {
          message_id: "m-2",
          role: "assistant",
          content: "La vigencia es hasta **2027-06-30** [Fuente 1].",
          sources: [
            {
              document_id: "doc-1",
              filename: "Contrato.pdf",
              chunk_index: 0,
              similarity: 0.95,
              content: "Vigencia hasta 2027-06-30.",
            },
          ],
        },
      ]);
    }
    if (path.includes("/conversations/") && path.endsWith("/documents")) {
      return json({ document_ids: [] });
    }
    if (path.endsWith("/agents/capabilities")) {
      return json({
        agents_enabled: true,
        code_mode_enabled: true,
        templates: [],
      });
    }
    if (path.endsWith("/agents/runs")) return json({ items: [] });
    if (path.endsWith("/agents/quota"))
      return json({ tokens_used: 0, tokens_limit: 10000 });
    if (path.endsWith("/documents/search"))
      return json({ items: [], total: 0, limit: 20, offset: 0 });
    if (
      [
        "/library/recent",
        "/library/favorites",
        "/folders",
        "/transfers",
        "/documents/assigned-to-me",
        "/documents/managed-by-me",
        "/documents/notifications",
      ].some((suffix) => path.endsWith(suffix))
    ) {
      return json(pageOf([]));
    }
    if (path.endsWith("/library/markers")) return json([]);
    if (path.endsWith("/google-drive/connection"))
      return json({ connected: false, enabled: false, version: 0 });
    return json({});
  });

  return errors;
}

test("KronDocs defaults to dark mode, loads SVG brand isotipo, switches themes, and supports editorial reading mode", async ({
  page,
}) => {
  const errors = await setupKronDocsMocks(page, { theme: null });
  await page.goto("/");

  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.locator("html")).toHaveAttribute(
    "data-theme-preference",
    "dark",
  );
  await expect(page).toHaveTitle(/KronDocs$/);

  const brandLoaded = await page
    .locator(".sidebar .brand-symbol-img")
    .evaluate((img) => img.complete && img.naturalWidth > 0);
  expect(brandLoaded).toBe(true);

  const editorialBtn = page.getByRole("button", { name: "Lectura" });
  await expect(editorialBtn).toBeVisible();
  await editorialBtn.click();
  await expect(editorialBtn).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".message-text.reading-mode-serif")).toBeVisible();

  await page.getByRole("button", { name: "Claro", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");

  await page.getByRole("button", { name: "Sistema", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute(
    "data-theme-preference",
    "system",
  );
  // Allow 180ms theme color transitions to settle before axe-core contrast scan.
  await page.waitForTimeout(260);

  const axe = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(axe.violations).toEqual([]);
  expect(errors).toEqual([]);
});

test("Document assignments view passes WCAG 2.2 AA in dark mode", async ({
  page,
}) => {
  const errors = await setupKronDocsMocks(page, { theme: "dark" });
  await page.goto("/documents/assignments");
  await expect(page.locator("main")).toBeVisible();
  const axe = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(axe.violations).toEqual([]);
  expect(errors).toEqual([]);
});
