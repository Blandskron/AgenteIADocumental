import assert from "node:assert/strict";
import test from "node:test";

import {
  cancelAgentRun,
  exportAgentRunContent,
  getAgentHealth,
  getAgentQuota,
  getAgentRun,
  listAgentRuns,
  listAgentTemplates,
  resumeAgentApproval,
  startAgentRun,
} from "../src/features/agents/api/agents.api.ts";

test("agents API client targets expected AgentOrchestratorServices endpoints", async () => {
  const calls = [];
  const client = async (path, options) => {
    calls.push({ path, options });
    if (path === "/api/v1/health") {
      return { status: "ok", agents_enabled: true, code_mode_enabled: false };
    }
    if (path === "/api/v1/agents/templates") {
      return {
        tenant_id: "t1",
        templates: [{ template_id: "contract_comparison", title: "Comparación" }],
      };
    }
    if (path === "/api/v1/agents/quota") {
      return {
        tenant_id: "t1",
        runs_used: 1,
        runs_limit: 200,
        tokens_used: 500,
        tokens_limit: 200000,
      };
    }
    if (path.includes("/export?format=csv")) {
      return "run_id,source_index\n";
    }
    if (path === "/api/v1/agents/runs" && options?.method === "POST") {
      return { run_id: "run_1", status: "WAITING_APPROVAL" };
    }
    if (path.startsWith("/api/v1/agents/runs?")) {
      return { items: [{ run_id: "run_1", status: "SUCCEEDED" }] };
    }
    if (path.endsWith("/resume")) {
      return { run_id: "run_1", status: "SUCCEEDED" };
    }
    if (path.endsWith("/cancel")) {
      return { run_id: "run_1", status: "CANCELLED" };
    }
    return { run_id: "run_1", status: "RUNNING" };
  };

  const health = await getAgentHealth(client);
  assert.equal(health.agents_enabled, true);

  const tpls = await listAgentTemplates(client);
  assert.equal(tpls.templates[0].template_id, "contract_comparison");

  const quota = await getAgentQuota(client);
  assert.equal(quota.tokens_limit, 200000);

  const csv = await exportAgentRunContent(client, "run_1", "csv");
  assert.match(csv, /run_id/);

  const created = await startAgentRun(client, {
    mode: "agent",
    goal: "Comparar contratos",
    document_ids: ["doc-1"],
    template_id: "contract_comparison",
  });
  assert.equal(created.run_id, "run_1");

  const listed = await listAgentRuns(client, 10);
  assert.equal(listed.items.length, 1);

  const fetched = await getAgentRun(client, "run_1");
  assert.equal(fetched.status, "RUNNING");

  const resumed = await resumeAgentApproval(client, "run_1", {
    approval_id: "apr_1",
    decision: "approve",
    comment: "OK",
  });
  assert.equal(resumed.status, "SUCCEEDED");

  const cancelled = await cancelAgentRun(client, "run_1");
  assert.equal(cancelled.status, "CANCELLED");

  assert.equal(calls.length, 9);
});
