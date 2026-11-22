import assert from "node:assert/strict";
import test from "node:test";

import {
  listAgentRunAudit,
  listAgentRuns,
  listAgentTemplates,
} from "../src/features/agents/api/agents.api.ts";
import {
  getOllamaPullStatus,
  listGroqModels,
  listOllamaModels,
} from "../src/features/settings-ai/api/settings-ai.api.ts";
import {
  listStudioArtifacts,
  listStudioJobs,
  listStudioTemplates,
} from "../src/features/studio/api/studio.api.ts";

test("Studio, SettingsAI and Agents API clients normalize missing arrays and forward AbortSignal", async () => {
  const controller = new AbortController();
  const seenSignals = [];
  const emptyClient = async (_path, options = {}) => {
    seenSignals.push(options.signal);
    return {};
  };

  const studioTpl = await listStudioTemplates(emptyClient, {
    signal: controller.signal,
  });
  assert.deepEqual(studioTpl.templates, []);

  const studioArt = await listStudioArtifacts(emptyClient, {
    signal: controller.signal,
  });
  assert.deepEqual(studioArt.items, []);

  const studioJobs = await listStudioJobs(emptyClient, {
    signal: controller.signal,
  });
  assert.deepEqual(studioJobs.items, []);

  const groqModels = await listGroqModels(emptyClient, {
    signal: controller.signal,
  });
  assert.deepEqual(groqModels.models, []);

  const ollamaModels = await listOllamaModels(emptyClient, {
    signal: controller.signal,
  });
  assert.deepEqual(ollamaModels.installed, []);
  assert.deepEqual(ollamaModels.catalog, []);

  const pullStatus = await getOllamaPullStatus(emptyClient, {
    signal: controller.signal,
  });
  assert.deepEqual(pullStatus.downloads, []);

  const agentRuns = await listAgentRuns(emptyClient, 10, {
    signal: controller.signal,
  });
  assert.deepEqual(agentRuns.items, []);

  const agentTemplates = await listAgentTemplates(emptyClient, {
    signal: controller.signal,
  });
  assert.deepEqual(agentTemplates.templates, []);

  const agentAudit = await listAgentRunAudit(emptyClient, "run_1", {
    signal: controller.signal,
  });
  assert.deepEqual(agentAudit.events, []);
  assert.equal(agentAudit.run_id, "run_1");

  assert.equal(seenSignals.length, 9);
  for (const sig of seenSignals) {
    assert.equal(sig, controller.signal);
  }
});
