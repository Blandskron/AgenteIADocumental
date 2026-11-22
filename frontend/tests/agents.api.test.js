import assert from "node:assert/strict";
import test from "node:test";

import {
  cancelAgentRun,
  getAgentHealth,
  getAgentRun,
  listAgentRuns,
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

  const created = await startAgentRun(client, {
    mode: "agent",
    goal: "Comparar contratos",
    document_ids: ["doc-1"],
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

  assert.equal(calls.length, 6);
});
