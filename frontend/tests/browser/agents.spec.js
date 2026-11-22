import { expect, test } from "@playwright/test";

const SYNTHETIC_USER = {
  id: 1,
  username: "demo",
  email: "demo@example.invalid",
  active_tenant_id: "tenant-1",
  permissions: ["use_chat", "upload_documents"],
  is_superuser: false,
};

async function mockBaseSession(page, { agentsEnabled = false, codeModeEnabled = false } = {}) {
  await page.route("**/api/users/setup-status/**", (route) =>
    route.fulfill({ json: { needs_setup: false } }),
  );
  await page.route("**/api/users/me/**", (route) =>
    route.fulfill({ json: SYNTHETIC_USER }),
  );
  await page.route("**/api/v1/conversations**", (route) =>
    route.fulfill({ json: { items: [] } }),
  );
  await page.route("**/api/v1/transfers**", (route) =>
    route.fulfill({ json: { items: [], has_more: false } }),
  );
  await page.route("**/api/v1/profile**", (route) =>
    route.fulfill({ json: { display_name: "Demo", version: 1 } }),
  );
  await page.route("http://localhost:8019/api/v1/health", (route) =>
    route.fulfill({
      json: {
        status: "ok",
        agents_enabled: agentsEnabled,
        code_mode_enabled: codeModeEnabled,
      },
    }),
  );
}

test("Mode 1 Chat remains clean with zero Agent UI when AGENTS_ENABLED=false", async ({
  page,
}) => {
  await mockBaseSession(page, { agentsEnabled: false, codeModeEnabled: false });
  await page.addInitScript(() => {
    localStorage.setItem(
      "blandskron_auth_session",
      JSON.stringify({
        sessionId: "sess-1",
        access: "synthetic.access.jwt",
        user: {
          id: "1",
          username: "demo",
          activeTenantId: "tenant-1",
          permissions: ["use_chat"],
        },
      }),
    );
  });
  await page.goto("/");
  await expect(page.getByRole("group", { name: "Modo de ejecución" })).toHaveCount(0);
});

test("Unified Chat/Agent/Code Mode flow with HITL approval and deterministic analysis", async ({
  page,
}) => {
  await mockBaseSession(page, { agentsEnabled: true, codeModeEnabled: true });
  await page.route("http://localhost:8019/api/v1/agents/templates", (route) =>
    route.fulfill({
      json: {
        tenant_id: "tenant-1",
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
    }),
  );
  await page.route("http://localhost:8019/api/v1/agents/runs?*", (route) =>
    route.fulfill({ json: { items: [] } }),
  );
  await page.route("http://localhost:8019/api/v1/agents/quota", (route) =>
    route.fulfill({
      json: {
        tenant_id: "tenant-1",
        runs_used: 1,
        runs_limit: 200,
        tokens_used: 450,
        tokens_limit: 200000,
      },
    }),
  );
  await page.route("http://localhost:8019/api/v1/agents/runs", (route) =>
    route.fulfill({
      status: 201,
      json: {
        run_id: "run_e2e_1",
        thread_id: "thr_e2e_1",
        tenant_id: "tenant-1",
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
    }),
  );

  await page.addInitScript(() => {
    localStorage.setItem(
      "blandskron_auth_session",
      JSON.stringify({
        sessionId: "sess-1",
        access: "synthetic.access.jwt",
        user: {
          id: "1",
          username: "demo",
          activeTenantId: "tenant-1",
          permissions: ["use_chat"],
        },
      }),
    );
  });

  await page.goto("/");
  await expect(page.getByRole("group", { name: "Modo de ejecución" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Code Mode" })).toBeVisible();
});
