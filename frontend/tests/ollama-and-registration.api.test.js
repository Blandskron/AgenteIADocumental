import assert from "node:assert/strict";
import test from "node:test";
import { createServer } from "vite";

test("registration, google OIDC, ollama and studio API adapters target expected endpoints", async () => {
  const origWindow = globalThis.window;
  globalThis.window = { location: { hostname: "localhost" } };
  const server = await createServer({
    configFile: false,
    resolve: { alias: { "@": new URL("../src", import.meta.url).pathname } },
    server: { middlewareMode: true, hmr: false },
    appType: "custom",
  });
  try {
    const authApi = await server.ssrLoadModule(
      "/src/features/auth/api/auth.api.ts",
    );
    const aiApi = await server.ssrLoadModule(
      "/src/features/settings-ai/api/settings-ai.api.ts",
    );
    const studioApi = await server.ssrLoadModule(
      "/src/features/studio/api/studio.api.ts",
    );

    const calls = [];
    const fakeClient = async (path, options = {}) => {
      calls.push({ path, method: options.method || "GET" });
      return {
        active_provider: "ollama",
        available_providers: ["groq", "ollama"],
        items: [],
      };
    };

    await aiApi.getActiveAIProvider(fakeClient);
    await aiApi.setActiveAIProvider(fakeClient, "ollama");
    await aiApi.getOllamaSettings(fakeClient);
    await aiApi.listOllamaModels(fakeClient);
    await aiApi.pullOllamaModel(fakeClient, "qwen2.5:3b");
    await aiApi.getOllamaPullStatus(fakeClient);
    await aiApi.testOllamaConnection(fakeClient, "qwen2.5:3b");
    await studioApi.listStudioArtifacts(fakeClient);
    await studioApi.listStudioJobs(fakeClient);

    assert.deepEqual(
      calls.map((c) => `${c.method} ${c.path}`),
      [
        "GET /api/integrations/ai/provider/",
        "PATCH /api/integrations/ai/provider/",
        "GET /api/integrations/ollama/",
        "GET /api/integrations/ollama/models/",
        "POST /api/integrations/ollama/pull/",
        "GET /api/integrations/ollama/pull/status/",
        "POST /api/integrations/ollama/test/",
        "GET /api/v1/studio/artifacts",
        "GET /api/v1/studio/jobs",
      ],
    );

    assert.equal(typeof authApi.setupStatusRequest, "function");
    assert.equal(typeof authApi.registerRequest, "function");
    assert.equal(typeof authApi.passwordResetRequest, "function");
    assert.equal(typeof authApi.googleOidcLoginRequest, "function");
  } finally {
    await server.close();
    if (origWindow === undefined) {
      delete globalThis.window;
    } else {
      globalThis.window = origWindow;
    }
  }
});

