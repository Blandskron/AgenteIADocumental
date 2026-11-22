import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";
import react from "@vitejs/plugin-react";

test("Agent UI components stay hidden when disabled and render accessible controls when enabled", async () => {
  const server = await createServer({
    configFile: false,
    plugins: [react()],
    resolve: {
      alias: {
        "@": new URL("../src", import.meta.url).pathname.replace(
          /^\/([A-Za-z]:)/,
          "$1",
        ),
      },
    },
    optimizeDeps: { noDiscovery: true, include: [] },
    server: { middlewareMode: true, hmr: false },
    appType: "custom",
  });

  try {
    const { AgentModeSelector } = await server.ssrLoadModule(
      "/src/features/agents/components/AgentModeSelector.tsx",
    );
    const { AgentRunPanel } = await server.ssrLoadModule(
      "/src/features/agents/components/AgentRunPanel.tsx",
    );
    const { AgentHistoryList } = await server.ssrLoadModule(
      "/src/features/agents/components/AgentHistoryList.tsx",
    );

    // 1. Disabled capabilities -> selector renders empty string (Mode 1 untouched)
    const disabledHtml = renderToStaticMarkup(
      React.createElement(AgentModeSelector, {
        mode: "chat",
        capabilities: {
          status: "ok",
          agents_enabled: false,
          code_mode_enabled: false,
        },
        onModeChange: () => {},
      }),
    );
    assert.equal(disabledHtml, "");

    // 2. Enabled capabilities -> selector renders Chat, Agente, Code Mode & templates
    const enabledHtml = renderToStaticMarkup(
      React.createElement(AgentModeSelector, {
        mode: "code_mode",
        capabilities: {
          status: "ok",
          agents_enabled: true,
          code_mode_enabled: true,
        },
        templates: [
          {
            template_id: "contract_comparison",
            title: "Comparación de contratos",
            description: "Compara contratos",
            recommended_mode: "code_mode",
            default_save_to_studio: false,
          },
        ],
        selectedTemplateId: "contract_comparison",
        onModeChange: () => {},
        onTemplateChange: () => {},
      }),
    );
    assert.match(enabledHtml, /Agente/);
    assert.match(enabledHtml, /Code Mode/);
    assert.match(enabledHtml, /Comparación de contratos/);

    // 3. AgentRunPanel renders approval card, steps, code viewer, export buttons and analysis
    const panelHtml = renderToStaticMarkup(
      React.createElement(AgentRunPanel, {
        run: {
          run_id: "run_ui_1",
          thread_id: "thr_ui_1",
          tenant_id: "t1",
          status: "SUCCEEDED",
          current_step: "completed",
          steps: [
            {
              index: 1,
              tool: "search_documents",
              status: "ok",
              duration_ms: 40,
            },
          ],
          pending_approval: {
            approval_id: "apr_1",
            action: "save_studio_artifact",
            summary: "Guardar informe",
          },
          sources: [
            {
              document_id: "doc-1",
              chunk_index: 0,
              quote: "Vencimiento 2027-06-30",
            },
          ],
          code_executions: [
            {
              code: "function transform(d){ return d; }",
              output: {},
              stdout: "",
              duration_ms: 12,
              evidence_count: 1,
            },
          ],
          result_markdown: "Resumen verificado [Fuente 1].",
          provider: "ollama",
          steps_used: 1,
          usage_tokens: 320,
        },
        quota: {
          tenant_id: "t1",
          runs_used: 2,
          runs_limit: 200,
          tokens_used: 320,
          tokens_limit: 200000,
        },
        analysis: {
          run_id: "run_ui_1",
          facts: {
            dates: [{ value: "2027-06-30", source_index: 1, document_id: "doc-1" }],
            amounts: [{ value: "USD 1500", source_index: 1, document_id: "doc-1" }],
          },
          expirations: {
            reference_date: "2026-11-22",
            total_dates: 1,
            summary: { expired: 0, urgent_30d: 0, upcoming_90d: 0, future: 1 },
            alerts: [
              {
                date: "2027-06-30",
                raw_date: "2027-06-30",
                days_remaining: 220,
                urgency: "FUTURE",
                document_id: "doc-1",
                chunk_index: 0,
                filename: "contrato.pdf",
                source_index: 1,
                quote: "Vencimiento 2027-06-30",
              },
            ],
          },
          comparison: { documents_compared: 1, comparison_markdown: "" },
        },
        busy: false,
        error: null,
        onCancel: () => {},
        onExport: () => {},
        onExportPdf: () => {},
        onAnalyze: () => {},
        onDecision: () => {},
        onDismiss: () => {},
      }),
    );
    assert.match(panelHtml, /Aprobación humana requerida/);
    assert.match(panelHtml, /Código auditado en sandbox/);
    assert.match(panelHtml, /Cuota: 320\/200000 tokens/);
    assert.match(panelHtml, /Fechas\/Montos/);
    assert.match(panelHtml, /USD 1500/);

    // 4. AgentHistoryList renders filter controls and runs
    const historyHtml = renderToStaticMarkup(
      React.createElement(AgentHistoryList, {
        runs: [
          {
            run_id: "run_h1",
            thread_id: "thr_h1",
            tenant_id: "t1",
            goal: "Comparar cláusulas",
            status: "SUCCEEDED",
            current_step: "completed",
            steps: [],
            pending_approval: null,
            sources: [],
            result_markdown: null,
            provider: "ollama",
            steps_used: 1,
            usage_tokens: 100,
          },
        ],
        activeRunId: "run_h1",
        onSelectRun: () => {},
      }),
    );
    assert.match(historyHtml, /Comparar cláusulas/);
    assert.match(historyHtml, /Filtrar historial del agente/);
  } finally {
    await server.close();
  }
});
