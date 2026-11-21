import assert from "node:assert/strict";
import test from "node:test";

import {
  deleteGroqCredentials,
  getGroqSettings,
  listGroqModels,
  patchGroqSettings,
  putGroqCredentials,
  testGroqConnection,
} from "../src/features/settings-ai/api/settings-ai.api.ts";

function makeClient(expectedPath, expectedMethod, response) {
  const calls = [];
  const client = async (path, options = {}) => {
    calls.push({ path, options });
    assert.equal(path, expectedPath);
    assert.equal(options.method, expectedMethod);
    return response;
  };
  return { client, calls };
}

test("settings-ai API adapter calls expected endpoints and never stores secrets", async () => {
  const getMock = makeClient("/api/integrations/groq/", "GET", {
    provider: "groq",
    configured: false,
    status: "not_configured",
  });
  const got = await getGroqSettings(getMock.client);
  assert.equal(got.status, "not_configured");

  const putMock = makeClient("/api/integrations/groq/credentials/", "PUT", {
    provider: "groq",
    configured: true,
    status: "ready_to_test",
    key_fingerprint: "a1b2",
  });
  const saved = await putGroqCredentials(putMock.client, "synthetic-groq-key");
  assert.equal(saved.key_fingerprint, "a1b2");
  assert.equal(JSON.parse(putMock.calls[0].options.body).api_key, "synthetic-groq-key");

  const patchMock = makeClient("/api/integrations/groq/", "PATCH", {
    provider: "groq",
    model: "llama-3.3-70b-versatile",
  });
  await patchGroqSettings(patchMock.client, { model: "llama-3.3-70b-versatile" });
  assert.equal(JSON.parse(patchMock.calls[0].options.body).model, "llama-3.3-70b-versatile");

  const modelsMock = makeClient("/api/integrations/groq/models/", "GET", {
    result: "ok",
    models: ["llama-3.3-70b-versatile"],
  });
  const models = await listGroqModels(modelsMock.client);
  assert.deepEqual(models.models, ["llama-3.3-70b-versatile"]);

  const testMock = makeClient("/api/integrations/groq/test/", "POST", {
    result: "ok",
    model: "llama-3.3-70b-versatile",
    checked_at: "2026-11-21T00:00:00Z",
  });
  const probe = await testGroqConnection(testMock.client, "llama-3.3-70b-versatile");
  assert.equal(probe.result, "ok");

  const delMock = makeClient("/api/integrations/groq/credentials/", "DELETE", {
    provider: "groq",
    configured: false,
    status: "not_configured",
  });
  const revoked = await deleteGroqCredentials(delMock.client);
  assert.equal(revoked.configured, false);
});

