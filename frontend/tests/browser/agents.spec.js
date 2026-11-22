import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
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
      tenant_name: "Empresa Demo",
      role: "TENANT_ADMIN",
      permissions: ["*"],
    },
  ],
};

async function prepareAgentPage(
  page,
  { agentsEnabled = false, codeModeEnabled = false, theme = "light" } = {},
) {
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
      localStorage.setItem("blandskron:theme", initialTheme);
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
    { user: normalizeAuthUser(identity), raw: identity, initialTheme: theme },
  );

  await page.route("**/test-api/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const method = route.request().method();

    if (path.endsWith("/api/users/me/")) return route.fulfill({ json: identity });
    if (path.endsWith("/api/users/setup-status/"))
      return route.fulfill({ json: { needs_setup: false } });
    if (path.endsWith("/api/v1/health")) {
      return route.fulfill({
        json: {
          status: "ok",
          agents_enabled: agentsEnabled,
          code_mode_enabled: codeModeEnabled,
        },
      });
    }
    if (path.endsWith("/api/v1/agents/templates")) {
      return route.fulfill({
        json: {
          tenant_id: "tenant-demo",
          templates: [
            {
              template_id: "contract_comparison",
              title: "Comparación de contratos",
              description: "Compara contratos",
              recommended_mode: "code_mode",
              default_save_to_studio: false,
            },
          ],
        },
      });
    }
    if (path.endsWith("/api/v1/agents/quota")) {
      return route.fulfill({
        json: {
          tenant_id: "tenant-demo",
          runs_used: 1,
          runs_limit: 200,
          tokens_used: 450,
          tokens_limit: 200000,
        },
      });
    }
    if (path.endsWith("/api/v1/agents/runs") && method === "GET") {
      return route.fulfill({ json: { items: [] } });
    }
    if (path.endsWith("/api/v1/agents/runs") && method === "POST") {
      return route.fulfill({
        status: 201,
        json: {
          run_id: "run_e2e_1",
          thread_id: "thr_e2e_1",
          tenant_id: "tenant-demo",
          goal: "Comparar vencimientos",
          status: "WAITING_APPROVAL",
          current_step: "human_approval",
          steps: [
            { index: 1, tool: "search_documents", status: "ok", duration_ms: 45 },
          ],
          pending_approval: {
            approval_id: "apr_e2e_1",
            action: "save_studio_artifact",
            summary: "Guardar comparativa en Knowledge Studio",
          },
          sources: [
            {
              document_id: "doc-1",
              chunk_index: 0,
              quote: "Vencimiento 2027-06-30, USD 5000",
            },
          ],
          result_markdown: "Resumen citado [Fuente 1].",
          provider: "ollama",
          steps_used: 1,
          usage_tokens: 450,
        },
      });
    }
    if (path.includes("/api/v1/conversations")) {
      return route.fulfill({ json: { items: [], has_more: false } });
    }
    if (path.includes("/api/v1/transfers")) {
      return route.fulfill({ json: { items: [], has_more: false } });
    }
    if (path.includes("/api/v1/profile")) {
      return route.fulfill({
        json: {
          display_name: "Usuario de prueba",
          email: "demo@example.invalid",
          version: 1,
        },
      });
    }
    if (path.endsWith("/api/integrations/ai/provider/")) {
      return route.fulfill({
        json: {
          active_provider: "groq",
          available_providers: ["groq", "ollama"],
        },
      });
    }
    if (path.endsWith("/api/integrations/groq/")) {
      return route.fulfill({
        json: {
          provider: "groq",
          configured: true,
          status: "connected",
          model: "llama-3.3-70b-versatile",
          params: { max_tokens: 2000, temperature: 0.3, timeout_seconds: 60 },
          last_check: { at: "2026-11-22T12:00:00Z", result: "ok" },
          key_fingerprint: "9f2a",
          encryption_ready: true,
          updated_at: "2026-11-22T12:00:00Z",
        },
      });
    }
    if (path.endsWith("/api/integrations/groq/models/")) {
      return route.fulfill({
        json: { result: "ok", models: ["llama-3.3-70b-versatile"] },
      });
    }
    if (path.endsWith("/api/audit-logs/")) {
      return route.fulfill({
        json: {
          total: 1,
          limit: 50,
          offset: 0,
          items: [
            {
              audit_id: "aud-1",
              tenant_id: "tenant-demo",
              actor_user_id: "123",
              action: "ai_settings_write",
              resource_type: "tenant_integration",
              resource_id: "groq",
              target_user_id: null,
              metadata: { provider: "groq" },
              created_at: "2026-11-22T12:00:00Z",
            },
          ],
        },
      });
    }
    return route.fulfill({ json: { items: [] } });
  });
}

test("Mode 1 Chat remains clean with zero Agent UI when AGENTS_ENABLED=false", async ({
  page,
}) => {
  await prepareAgentPage(page, { agentsEnabled: false, codeModeEnabled: false });
  await page.goto("/");
  await expect(
    page.getByRole("group", { name: "Modo de ejecución" }),
  ).toHaveCount(0);
});

test("Unified Chat/Agent/Code Mode renders selector when AGENTS_ENABLED=true", async ({
  page,
}) => {
  await prepareAgentPage(page, { agentsEnabled: true, codeModeEnabled: true });
  await page.goto("/");
  await expect(
    page.getByRole("group", { name: "Modo de ejecución" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Code Mode" })).toBeVisible();
});

for (const theme of ["light", "dark"]) {
  test(`New views (/settings/ai, /studio, /admin/audit, AgentRunPanel) pass WCAG axe checks in ${theme} theme`, async ({
    page,
  }) => {
    await prepareAgentPage(page, {
      agentsEnabled: true,
      codeModeEnabled: true,
      theme,
    });

    await page.goto("/settings/ai");
    await expect(
      page.getByRole("heading", { name: "Proveedor Groq (Generación)" }),
    ).toBeVisible();
    const aiScan = await new AxeBuilder({ page }).analyze();
    expect(aiScan.violations).toEqual([]);

    await page.goto("/studio");
    await expect(
      page.getByRole("heading", { name: "Knowledge Studio", exact: true }),
    ).toBeVisible();
    const studioScan = await new AxeBuilder({ page }).analyze();
    expect(studioScan.violations).toEqual([]);

    await page.goto("/admin/audit");
    await expect(
      page.getByRole("heading", { name: "Auditoría de seguridad", exact: true }),
    ).toBeVisible();
    await expect(page.getByText("ai_settings_write")).toBeVisible();
    const auditScan = await new AxeBuilder({ page }).analyze();
    expect(auditScan.violations).toEqual([]);

    await page.goto("/");
    await page.getByRole("button", { name: "Agente", exact: true }).click();
    await page.getByRole("textbox").fill("Comparar vencimientos");
    await page.getByRole("textbox").press("Enter");
    await expect(
      page.getByRole("region", { name: "Estado de ejecución del agente" }),
    ).toBeVisible();
    const agentPanelScan = await new AxeBuilder({ page }).analyze();
    expect(agentPanelScan.violations).toEqual([]);
  });
}
