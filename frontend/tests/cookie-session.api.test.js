import assert from "node:assert/strict";
import test from "node:test";
import { createServer } from "vite";

test("cookie session helpers send credentials include and X-CSRFToken", async () => {
  const origWindow = globalThis.window;
  globalThis.window = { location: { hostname: "localhost" } };
  const server = await createServer({
    configFile: false,
    resolve: { alias: { "@": new URL("../src", import.meta.url).pathname } },
    server: { middlewareMode: true, hmr: false },
    appType: "custom",
  });
  try {
    const mod = await server.ssrLoadModule("/src/features/auth/api/auth.api.ts");
    assert.equal(
      mod.readCsrfToken("foo=1; csrftoken=abc%2D123; bar=2"),
      "abc-123",
    );
    assert.equal(mod.readCsrfToken("foo=1"), null);

    const calls = [];
    const origFetch = globalThis.fetch;
    globalThis.fetch = async (url, init) => {
      calls.push({ url: String(url), init });
      return new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };
    try {
      await mod.cookieLoginRequest(
        { username: "demo", password: "secret" },
        "csrf-tok-1",
      );
      await mod.cookieRefreshRequest("csrf-tok-1");
      await mod.cookieLogoutRequest("csrf-tok-1");
    } finally {
      globalThis.fetch = origFetch;
    }

    assert.equal(calls.length, 3);
    assert.ok(calls[0].url.endsWith("/api/users/session/login/"));
    assert.equal(calls[0].init.credentials, "include");
    assert.equal(calls[0].init.headers["X-CSRFToken"], "csrf-tok-1");
    assert.ok(calls[1].url.endsWith("/api/users/session/refresh/"));
    assert.ok(calls[2].url.endsWith("/api/users/session/logout/"));
    assert.equal(calls[2].init.keepalive, true);
  } finally {
    await server.close();
    if (origWindow === undefined) {
      delete globalThis.window;
    } else {
      globalThis.window = origWindow;
    }
  }
});

