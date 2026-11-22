#!/usr/bin/env node
/**
 * Captures high-resolution (1280x800 @2x) real-UI screenshots of Blandskron Documental
 * against the built React frontend (`vite preview`) using synthetic data (zero secrets/PII).
 * Outputs optimized WebP assets into `docs/assets/screenshots/`.
 */

import { spawn, execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "../..");
const FRONTEND_DIR = path.join(ROOT, "frontend");
const OUT_DIR = path.join(ROOT, "docs", "assets", "screenshots");
const PORT = 4179;
const BASE_URL = `http://127.0.0.1:${PORT}`;

const IDENTITY = {
  id: 123,
  username: "ana.martinez",
  display_name: "Ana Martínez",
  email: "ana.martinez@empresa-demo.invalid",
  is_superuser: true,
  active_tenant_id: "tenant-demo",
  active_role: "TENANT_ADMIN",
  active_permissions: ["*"],
  tenant_memberships: [
    {
      tenant_id: "tenant-demo",
      tenant_name: "Blandskron Legal & Ops",
      role: "TENANT_ADMIN",
      permissions: ["*"],
    },
  ],
};

const NORMALIZED_USER = {
  id: "123",
  username: "ana.martinez",
  displayName: "Ana Martínez",
  email: "ana.martinez@empresa-demo.invalid",
  isSuperuser: true,
  isSuperadmin: true,
  activeTenantId: "tenant-demo",
  activeTenantName: "Blandskron Legal & Ops",
  activeRole: "TENANT_ADMIN",
  activePermissions: ["*"],
  permissions: ["*"],
  tenantMemberships: [
    {
      tenantId: "tenant-demo",
      tenantName: "Blandskron Legal & Ops",
      role: "TENANT_ADMIN",
      permissions: ["*"],
    },
  ],
};

const SYNTHETIC_DOCS = [
  {
    document_id: "doc-001",
    filename: "Contrato_Marco_Servicios_2026.pdf",
    mime_type: "application/pdf",
    status: "PROCESSED",
    chunk_count: 14,
    size_bytes: 428120,
    is_favorite: true,
    snippet: "Cláusula 8: Penalización del 2.5% mensual por retraso. Vigencia hasta 2027-06-30.",
    updated_at: "2026-11-18T14:20:00Z",
    created_at: "2026-11-10T09:15:00Z",
  },
  {
    document_id: "doc-002",
    filename: "Anexo_Tarifas_SLA_2026.pdf",
    mime_type: "application/pdf",
    status: "PROCESSED",
    chunk_count: 8,
    size_bytes: 215400,
    is_favorite: true,
    snippet: "Tarifa base mensual USD 4,500.00 con disponibilidad garantizada del 99.9%.",
    updated_at: "2026-11-19T11:05:00Z",
    created_at: "2026-11-12T10:30:00Z",
  },
  {
    document_id: "doc-003",
    filename: "Politica_Seguridad_Informacion.md",
    mime_type: "text/markdown",
    status: "PROCESSED",
    chunk_count: 11,
    size_bytes: 64200,
    is_favorite: false,
    snippet: "Control de acceso basado en roles (RBAC), rotación de claves cada 90 días y auditoría.",
    updated_at: "2026-11-20T16:45:00Z",
    created_at: "2026-11-15T08:00:00Z",
  },
  {
    document_id: "doc-004",
    filename: "Acta_Comite_Cumplimiento_Q4.docx",
    mime_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    status: "PROCESSED",
    chunk_count: 6,
    size_bytes: 184320,
    is_favorite: false,
    snippet: "Revisión trimestral aprobada con vencimiento de auditoría externa 15/12/2026.",
    updated_at: "2026-11-21T09:30:00Z",
    created_at: "2026-11-21T09:00:00Z",
  },
];

const SYNTHETIC_CONVERSATIONS = [
  {
    conversation_id: "conv-demo-1",
    id: "conv-demo-1",
    title: "Revisión de penalizaciones y SLA 2026",
    created_at: "2026-11-21T10:00:00Z",
    updated_at: "2026-11-21T10:04:00Z",
    selected_documents: [
      { document_id: "doc-001", filename: "Contrato_Marco_Servicios_2026.pdf" },
      { document_id: "doc-002", filename: "Anexo_Tarifas_SLA_2026.pdf" },
    ],
    messages: [
      {
        id: "m-1",
        role: "user",
        content:
          "¿Cuáles son las penalizaciones por retraso, la tarifa mensual y la fecha de vigencia en los contratos seleccionados?",
        created_at: "2026-11-21T10:01:00Z",
      },
      {
        id: "m-2",
        role: "assistant",
        content: [
          "### Resumen contractual verificado",
          "",
          "Con base en los documentos autorizados seleccionados:",
          "",
          "- **Penalización por retraso:** se establece un recargo del **2.5% mensual** sobre el importe vencido según la Cláusula 8 [Fuente 1].",
          "- **Vigencia del contrato:** el acuerdo permanece vigente hasta el **2027-06-30** con renovación sujeta a preaviso de 30 días [Fuente 1].",
          "- **Tarifa y SLA:** la tarifa base mensual es de **USD 4,500.00** con una disponibilidad garantizada del **99.9%** [Fuente 2].",
        ].join("\n"),
        sources: [
          {
            document_id: "doc-001",
            filename: "Contrato_Marco_Servicios_2026.pdf",
            chunk_index: 8,
            similarity: 0.94,
            content:
              "Cláusula 8: Penalización del 2.5% mensual por retraso. Vigencia hasta 2027-06-30 con preaviso de 30 días.",
          },
          {
            document_id: "doc-002",
            filename: "Anexo_Tarifas_SLA_2026.pdf",
            chunk_index: 2,
            similarity: 0.91,
            content:
              "Tarifa base mensual USD 4,500.00 con disponibilidad garantizada del 99.9% en horario operativo.",
          },
        ],
        created_at: "2026-11-21T10:01:12Z",
      },
    ],
  },
];

async function waitForServer(url, timeoutMs = 15000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    try {
      const resp = await fetch(url);
      if (resp.ok) return;
    } catch {
      // Wait for Vite preview to bind.
    }
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(`Vite preview did not respond at ${url}`);
}

async function attachApiMocks(page, { authenticated = true } = {}) {
  await page.addInitScript(
    ({ user, raw, authenticated }) => {
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
      localStorage.setItem("blandskron:theme", "light");
      if (authenticated) {
        localStorage.setItem(
          "blandskron.auth",
          JSON.stringify({
            user,
            access: `synthetic.${btoa(JSON.stringify(raw))}.synthetic`,
            refresh: "synthetic-refresh",
            username: raw.username,
            sessionId: "11111111-1111-1111-1111-111111111111",
          }),
        );
      } else {
        localStorage.removeItem("blandskron.auth");
      }
    },
    { user: NORMALIZED_USER, raw: IDENTITY, authenticated },
  );

  await page.route("**/test-api/**", async (route) => {
    const url = new URL(route.request().url());
    const p = url.pathname;
    const method = route.request().method();

    if (p.endsWith("/api/users/setup-status/")) {
      return route.fulfill({ json: { needs_setup: false } });
    }
    if (p.endsWith("/api/users/me/")) {
      return route.fulfill({ json: IDENTITY });
    }
    if (p.endsWith("/api/v1/health")) {
      return route.fulfill({
        json: {
          status: "ok",
          agents_enabled: true,
          code_mode_enabled: true,
          studio_enabled: true,
        },
      });
    }
    if (p.endsWith("/api/v1/conversations") || p.endsWith("/api/v1/conversations/")) {
      return route.fulfill({
        json: {
          items: SYNTHETIC_CONVERSATIONS,
          total: 1,
          limit: 50,
          offset: 0,
          has_more: false,
        },
      });
    }
    if (p.includes("/api/v1/conversations/conv-demo-1")) {
      return route.fulfill({ json: SYNTHETIC_CONVERSATIONS[0] });
    }
    if (p.includes("/api/v1/documents/search") || p.endsWith("/api/v1/documents")) {
      return route.fulfill({
        json: {
          items: SYNTHETIC_DOCS,
          documents: SYNTHETIC_DOCS,
          total: SYNTHETIC_DOCS.length,
          limit: 50,
          offset: 0,
          has_more: false,
        },
      });
    }
    if (p.endsWith("/library/markers")) {
      return route.fulfill({
        json: SYNTHETIC_DOCS.map((doc) => ({
          document_id: doc.document_id,
          is_favorite: Boolean(doc.is_favorite),
        })),
      });
    }
    if (p.endsWith("/folders") || p.includes("/api/v1/library/folders")) {
      return route.fulfill({
        json: {
          items: [
            {
              folder_id: "fld-1",
              name: "Contratos 2026",
              parent_folder_id: null,
              owner_user_id: "123",
              document_count: 2,
              metadata: {},
            },
            {
              folder_id: "fld-2",
              name: "Políticas y Cumplimiento",
              parent_folder_id: null,
              owner_user_id: "123",
              document_count: 2,
              metadata: {},
            },
          ],
          limit: 50,
          offset: 0,
          total: 2,
          has_more: false,
        },
      });
    }
    if (p.includes("/api/v1/library/favorites")) {
      return route.fulfill({
        json: { items: SYNTHETIC_DOCS.slice(0, 2), limit: 50, offset: 0, total: 2, has_more: false },
      });
    }
    if (p.includes("/api/v1/library/recent")) {
      return route.fulfill({
        json: { items: SYNTHETIC_DOCS, limit: 50, offset: 0, total: 4, has_more: false },
      });
    }
    if (
      p.endsWith("/documents/assigned-to-me") ||
      p.endsWith("/documents/managed-by-me") ||
      p.includes("/api/v1/assignments") ||
      p.includes("/api/v1/documents/assignments")
    ) {
      return route.fulfill({
        json: {
          items: [
            {
              assignment_id: "asg-1",
              document_id: "doc-001",
              document_filename: "Contrato_Marco_Servicios_2026.pdf",
              filename: "Contrato_Marco_Servicios_2026.pdf",
              assigned_to_user_id: "123",
              assigned_to_username: "ana.martinez",
              assigned_by_username: "direccion.legal",
              status: "PENDING",
              requires_signature: true,
              due_at: "2026-12-05T18:00:00Z",
              note: "Revisar cláusula de penalización y confirmar aceptación antes del cierre Q4.",
              created_at: "2026-11-20T12:00:00Z",
            },
            {
              assignment_id: "asg-2",
              document_id: "doc-003",
              document_filename: "Politica_Seguridad_Informacion.md",
              filename: "Politica_Seguridad_Informacion.md",
              assigned_to_user_id: "123",
              assigned_to_username: "ana.martinez",
              assigned_by_username: "seguridad.ti",
              status: "ACCEPTED",
              requires_signature: true,
              due_at: "2026-11-18T18:00:00Z",
              note: "Lectura obligatoria de política de rotación de claves.",
              created_at: "2026-11-12T09:00:00Z",
            },
          ],
          limit: 50,
          offset: 0,
          total: 2,
          has_more: false,
        },
      });
    }
    if (p.includes("/api/integrations/ai/provider")) {
      return route.fulfill({ json: { active_provider: "ollama", available_providers: ["groq", "ollama"] } });
    }
    if (p.includes("/api/integrations/groq/models")) {
      return route.fulfill({
        json: {
          models: ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
        },
      });
    }
    if (p.includes("/api/integrations/groq")) {
      return route.fulfill({
        json: {
          status: "connected",
          has_api_key: true,
          masked_api_key: "gsk_••••••••demo",
          model: "llama-3.3-70b-versatile",
          params: { max_tokens: 2000, temperature: 0.2, timeout_seconds: 60 },
          updated_at: "2026-11-21T14:00:00Z",
        },
      });
    }
    if (p.includes("/api/integrations/ollama/models") || p.includes("/api/integrations/ollama/catalog")) {
      return route.fulfill({
        json: {
          reachable: true,
          status: "connected",
          installed: [
            { name: "qwen2.5:3b", size_bytes: 1930000000 },
            { name: "gemma2:2b", size_bytes: 1620000000 },
          ],
          catalog: [
            {
              id: "qwen2.5:3b",
              name: "qwen2.5:3b",
              label: "Qwen 2.5 3B (Recomendado CPU)",
              size_gb: 1.9,
              ram_gb: 6,
              recommended: true,
              installed: true,
            },
            {
              id: "gemma2:2b",
              name: "gemma2:2b",
              label: "Gemma 2 2B (Ligero CPU)",
              size_gb: 1.6,
              ram_gb: 4,
              recommended: false,
              installed: true,
            },
            {
              id: "llama3.2:3b",
              name: "llama3.2:3b",
              label: "Llama 3.2 3B (Equilibrado)",
              size_gb: 2.0,
              ram_gb: 6,
              recommended: false,
              installed: false,
            },
          ],
        },
      });
    }
    if (p.includes("/api/integrations/ollama/pull")) {
      return route.fulfill({ json: { downloads: [] } });
    }
    if (p.includes("/api/integrations/ollama")) {
      return route.fulfill({
        json: {
          status: "connected",
          base_url: "http://ollama:11434",
          model: "qwen2.5:3b",
          installed_models: ["qwen2.5:3b", "gemma2:2b"],
          params: { max_tokens: 2000, temperature: 0.2, timeout_seconds: 120 },
        },
      });
    }
    if (p.includes("/api/v1/studio/artifacts")) {
      return route.fulfill({
        json: {
          items: [
            {
              artifact_id: "art-001",
              template_id: "summary.executive",
              title: "Resumen Ejecutivo — Contratos y SLA 2026",
              status: "FRESH",
              version: 2,
              document_ids: ["doc-001", "doc-002"],
              created_at: "2026-11-21T11:30:00Z",
              content: {
                summary: "Vigencia hasta 2027-06-30 con tarifa USD 4,500.00 y SLA 99.9% [Fuente 1] [Fuente 2].",
              },
            },
            {
              artifact_id: "art-002",
              template_id: "evidence_table",
              title: "Matriz Comparativa de Cláusulas y Vencimientos",
              status: "FRESH",
              version: 1,
              document_ids: ["doc-001", "doc-004"],
              created_at: "2026-11-21T12:15:00Z",
              content: {
                summary: "2 vencimientos próximos y 1 cláusula de penalización del 2.5% mensual.",
              },
            },
          ],
        },
      });
    }
    if (p.includes("/api/v1/studio/jobs")) {
      return route.fulfill({ json: { items: [] } });
    }
    if (p.endsWith("/api/v1/agents/templates")) {
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
            {
              template_id: "dates_amounts_extraction",
              title: "Fechas, montos y vencimientos",
              description: "Extrae fechas y montos",
              recommended_mode: "code_mode",
              default_save_to_studio: false,
            },
          ],
        },
      });
    }
    if (p.endsWith("/api/v1/agents/quota")) {
      return route.fulfill({
        json: {
          tenant_id: "tenant-demo",
          runs_used: 4,
          runs_limit: 200,
          tokens_used: 3420,
          tokens_limit: 200000,
        },
      });
    }
    if (p.endsWith("/api/v1/agents/runs") && method === "GET") {
      return route.fulfill({
        json: {
          items: [
            {
              run_id: "run_ag_001",
              thread_id: "thr_ag_001",
              tenant_id: "tenant-demo",
              goal: "Comparar cláusulas de penalización y detectar vencimientos Q4",
              status: "WAITING_APPROVAL",
              current_step: "human_approval",
              steps: [
                { index: 1, tool: "search_documents_fts", status: "ok", duration_ms: 48 },
                { index: 2, tool: "get_document_chunks", status: "ok", duration_ms: 62 },
                { index: 3, tool: "execute_code", status: "ok", duration_ms: 34 },
              ],
              pending_approval: {
                approval_id: "apr_001",
                action: "save_studio_artifact",
                summary: "Guardar tabla comparativa verificada en Knowledge Studio (2 fuentes citadas)",
              },
              sources: [
                {
                  source_index: 1,
                  document_id: "doc-001",
                  chunk_index: 8,
                  filename: "Contrato_Marco_Servicios_2026.pdf",
                  quote: "Penalización del 2.5% mensual. Vigencia hasta 2027-06-30.",
                },
                {
                  source_index: 2,
                  document_id: "doc-004",
                  chunk_index: 1,
                  filename: "Acta_Comite_Cumplimiento_Q4.docx",
                  quote: "Vencimiento de auditoría externa 15/12/2026.",
                },
              ],
              code_executions: [
                {
                  code: "function transform(data) {\n  return { total_usd: 4500, expiring_30d: 1 };\n}",
                  output: { total_usd: 4500, expiring_30d: 1 },
                  stdout: "",
                  duration_ms: 34,
                  evidence_count: 2,
                },
              ],
              result_markdown:
                "**Comparativa ejecutada en sandbox:** tarifa mensual `USD 4,500.00`, penalización `2.5%` [Fuente 1] y **1 vencimiento urgente** el `15/12/2026` [Fuente 2].",
              provider: "ollama",
              steps_used: 3,
              usage_tokens: 1180,
            },
          ],
        },
      });
    }
    if (p.endsWith("/api/v1/agents/runs") && method === "POST") {
      return route.fulfill({
        status: 201,
        json: {
          run_id: "run_ag_001",
          thread_id: "thr_ag_001",
          tenant_id: "tenant-demo",
          goal: "Comparar cláusulas de penalización y detectar vencimientos Q4",
          status: "WAITING_APPROVAL",
          current_step: "human_approval",
          steps: [
            { index: 1, tool: "search_documents_fts", status: "ok", duration_ms: 48 },
            { index: 2, tool: "get_document_chunks", status: "ok", duration_ms: 62 },
            { index: 3, tool: "execute_code", status: "ok", duration_ms: 34 },
          ],
          pending_approval: {
            approval_id: "apr_001",
            action: "save_studio_artifact",
            summary: "Guardar tabla comparativa verificada en Knowledge Studio (2 fuentes citadas)",
          },
          sources: [
            {
              source_index: 1,
              document_id: "doc-001",
              chunk_index: 8,
              filename: "Contrato_Marco_Servicios_2026.pdf",
              quote: "Penalización del 2.5% mensual. Vigencia hasta 2027-06-30.",
            },
            {
              source_index: 2,
              document_id: "doc-004",
              chunk_index: 1,
              filename: "Acta_Comite_Cumplimiento_Q4.docx",
              quote: "Vencimiento de auditoría externa 15/12/2026.",
            },
          ],
          code_executions: [
            {
              code: "function transform(data) {\n  return { total_usd: 4500, expiring_30d: 1 };\n}",
              output: { total_usd: 4500, expiring_30d: 1 },
              stdout: "",
              duration_ms: 34,
              evidence_count: 2,
            },
          ],
          result_markdown:
            "**Comparativa ejecutada en sandbox:** tarifa mensual `USD 4,500.00`, penalización `2.5%` [Fuente 1] y **1 vencimiento urgente** el `15/12/2026` [Fuente 2].",
          provider: "ollama",
          steps_used: 3,
          usage_tokens: 1180,
        },
      });
    }
    if (p.includes("/api/v1/profile")) {
      return route.fulfill({
        json: {
          display_name: "Ana Martínez",
          email: "ana.martinez@empresa-demo.invalid",
          version: 1,
        },
      });
    }
    if (p.includes("/api/v1/transfers") || p.includes("/api/v1/exports")) {
      return route.fulfill({ json: { items: [], has_more: false } });
    }
    return route.fulfill({ json: { items: [] } });
  });
}

function convertPngsToWebp(names) {
  const pyCode = `
from pathlib import Path
from PIL import Image
out = Path(${JSON.stringify(OUT_DIR)})
for name in ${JSON.stringify(names)}:
    png = out / f"{name}.png"
    webp = out / f"{name}.webp"
    if png.is_file():
        with Image.open(png) as img:
            img.save(webp, "WEBP", quality=88, method=6)
        png.unlink()
        print(f"Converted {webp.name} ({webp.stat().st_size // 1024} KB)")
`;
  execFileSync("python", ["-c", pyCode], { stdio: "inherit" });
}

async function main() {
  fs.mkdirSync(OUT_DIR, { recursive: true });

  const vite = spawn(
    process.platform === "win32" ? "npx.cmd" : "npx",
    ["vite", "preview", "--host", "127.0.0.1", "--port", String(PORT), "--strictPort"],
    { cwd: FRONTEND_DIR, stdio: "ignore", shell: process.platform === "win32" },
  );

  try {
    await waitForServer(BASE_URL);
    const { chromium } = await import(
      `file://${path.join(FRONTEND_DIR, "node_modules", "@playwright", "test", "index.mjs").replace(/\\/g, "/")}`
    );

    const browser = await chromium.launch({ headless: true });
    const captured = [];

    try {
      // 1. Login screen (unauthenticated)
      {
        const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 2 });
        const page = await ctx.newPage();
        await attachApiMocks(page, { authenticated: false });
        await page.goto(`${BASE_URL}/login`, { waitUntil: "networkidle" });
        await page.waitForTimeout(500);
        await page.screenshot({ path: path.join(OUT_DIR, "login.png") });
        captured.push("login");
        await ctx.close();
      }

      // 2. Authenticated screens
      const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 2 });
      const page = await ctx.newPage();
      await attachApiMocks(page, { authenticated: true });

      // 2a. Chat documental
      await page.goto(`${BASE_URL}/`, { waitUntil: "networkidle" });
      await page.waitForTimeout(700);
      await page.screenshot({ path: path.join(OUT_DIR, "document-chat.png") });
      captured.push("document-chat");

      // 2b. Agent Orchestrator + Code Mode + HITL approval
      const codeModeBtn = page.getByRole("button", { name: "Code Mode" });
      if (await codeModeBtn.isVisible()) {
        await codeModeBtn.click();
      }
      const historySummary = page.locator("summary", { hasText: "Historial de ejecuciones" });
      if (await historySummary.isVisible()) {
        await historySummary.click();
        await page.waitForTimeout(250);
        const runBtn = page.locator("button", { hasText: "Comparar cláusulas" }).first();
        if (await runBtn.isVisible()) {
          await runBtn.click();
          await page.waitForTimeout(500);
        }
      }
      await page.screenshot({ path: path.join(OUT_DIR, "agent-orchestrator.png") });
      captured.push("agent-orchestrator");

      // 2c. Documents library & search
      await page.goto(`${BASE_URL}/documents`, { waitUntil: "networkidle" });
      await page.waitForTimeout(700);
      await page.screenshot({ path: path.join(OUT_DIR, "documents.png") });
      captured.push("documents");

      // 2d. AI Settings (Groq & Ollama)
      await page.goto(`${BASE_URL}/settings/ai`, { waitUntil: "networkidle" });
      await page.waitForTimeout(700);
      await page.screenshot({ path: path.join(OUT_DIR, "ai-settings.png") });
      captured.push("ai-settings");

      // 2e. Knowledge Studio
      await page.goto(`${BASE_URL}/studio`, { waitUntil: "networkidle" });
      await page.waitForTimeout(700);
      await page.screenshot({ path: path.join(OUT_DIR, "knowledge-studio.png") });
      captured.push("knowledge-studio");

      // 2f. Document Assignments
      await page.goto(`${BASE_URL}/documents/assignments`, { waitUntil: "networkidle" });
      await page.waitForTimeout(700);
      await page.screenshot({ path: path.join(OUT_DIR, "document-assignments.png") });
      captured.push("document-assignments");

      await ctx.close();
    } finally {
      await browser.close();
    }

    convertPngsToWebp(captured);
    console.log(`Successfully generated ${captured.length} WebP screenshots in docs/assets/screenshots/`);
  } finally {
    vite.kill();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
