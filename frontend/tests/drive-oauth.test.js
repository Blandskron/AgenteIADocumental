import test from "node:test";
import assert from "node:assert/strict";
import { webcrypto } from "node:crypto";
import { completeDriveAuthorization, startDriveAuthorization } from "../src/features/google-drive-import/oauth-flow.js";

function browser(path = "/documents") {
  const storage = new Map();
  const view = { crypto: webcrypto, sessionStorage: {
    setItem: (key, value) => storage.set(key, value), getItem: (key) => storage.get(key), removeItem: (key) => storage.delete(key),
  }, location: { origin: "https://portfolio.test", href: `https://portfolio.test${path}`, assign: (value) => { view.assigned = value; } },
  history: { replaceState: (_, __, value) => { view.location.href = `https://portfolio.test${value}`; } } };
  return view;
}

function api(view) {
  const calls = [];
  const client = async (path, options) => {
    const payload = JSON.parse(options.body); calls.push({ path, payload });
    if (path.endsWith("auth-url")) {
      const state = "s".repeat(43), redirect = "https://portfolio.test/documents";
      const url = new URL("https://accounts.google.com/o/oauth2/v2/auth");
      Object.entries({ state, code_challenge: payload.code_challenge, code_challenge_method: "S256", redirect_uri: redirect }).forEach(([key, value]) => url.searchParams.set(key, value));
      return { state, authorization_url: url.href, redirect_uri: redirect };
    }
    return { connected: true, provider_account_id: "synthetic" };
  };
  return { client, calls };
}

test("PKCE verifier stays in tab storage; callback coalesces and strips OAuth query", async () => {
  const view = browser(), { client, calls } = api(view);
  await startDriveAuthorization(client, "session-one", view);
  assert.equal(calls[0].payload.code_challenge.length, 43);
  view.location.href += "?code=synthetic-code&state=" + "s".repeat(43) + "&iss=https%3A%2F%2Faccounts.google.com&keep=yes";
  const first = completeDriveAuthorization(client, "session-one", view);
  assert.equal(first, completeDriveAuthorization(client, "session-one", view));
  assert.equal(view.location.href, "https://portfolio.test/documents?keep=yes");
  assert.equal((await first).connected, true);
  assert.equal(calls.length, 2);
  assert.notEqual(calls[1].payload.code_verifier, calls[0].payload.code_challenge);
  assert.equal(view.sessionStorage.getItem("blandskron.drive.oauth.v1"), undefined);
});

for (const mutation of ["no_attempt", "account", "tenant", "state", "path", "duplicate", "provider_error", "issuer", "expired"]) {
  test(`callback rejects ${mutation} without exchanging code and cleans URL`, async () => {
    const view = browser(), { client, calls } = api(view);
    if (mutation !== "no_attempt") await startDriveAuthorization(client, "session-one", view);
    view.location.href = "https://portfolio.test/documents?code=synthetic&state=" + "s".repeat(43);
    let scope = "session-one";
    if (["account", "tenant"].includes(mutation)) scope = mutation;
    if (mutation === "state") view.location.href = view.location.href.replace("state=s", "state=x");
    if (mutation === "path") view.location.href = view.location.href.replace("/documents", "/applications/google-drive");
    if (mutation === "duplicate") view.location.href += "&code=another";
    if (mutation === "provider_error") view.location.href += "&error=access_denied&error_description=private";
    if (mutation === "issuer") view.location.href += "&iss=https://evil.test";
    if (mutation === "expired") {
      const key = "blandskron.drive.oauth.v1", value = JSON.parse(view.sessionStorage.getItem(key));
      value.createdAt -= 301000; view.sessionStorage.setItem(key, JSON.stringify(value));
    }
    await assert.rejects(completeDriveAuthorization(client, scope, view), /autorización/);
    assert.equal(calls.filter((call) => call.path.endsWith("callback")).length, 0);
    assert.equal(new URL(view.location.href).search, "");
  });
}
