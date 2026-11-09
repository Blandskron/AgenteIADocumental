import test from "node:test";
import assert from "node:assert/strict";
import { openGoogleDrivePicker } from "../src/features/google-drive-import/google-picker.js";

test("disabled integration cannot contact Google even with an existing connection", async () => {
  await assert.rejects(openGoogleDrivePicker({ appId: "123", clientId: "client", developerKey: "synthetic",
    connection: { enabled: false, connected: true, oauthClientId: "client", pickerAppId: "123", providerAccountId: "account-one" } }), /aplicación y cuenta/);
});

test("Picker rejects a different OAuth client before loading Google scripts", async () => {
  await assert.rejects(openGoogleDrivePicker({ appId: "123", clientId: "different", developerKey: "synthetic",
    connection: { enabled: true, connected: true, oauthClientId: "expected", pickerAppId: "123", providerAccountId: "account-one" } }), /aplicación y cuenta/);
});

test("Picker checks Drive account before opening and never sends its ephemeral token to the backend", async (context) => {
  let opened = 0;
  context.mock.method(globalThis, "fetch", async (url, options) => {
    assert.equal(new URL(url).origin, "https://www.googleapis.com");
    assert.equal(options.headers.Authorization, "Bearer synthetic-ephemeral");
    return { ok: true, json: async () => ({ user: { permissionId: "another-account" } }) };
  });
  const previous = globalThis.window;
  globalThis.window = { gapi: { load: (_, config) => config.callback() }, google: {
    accounts: { oauth2: { initTokenClient: (config) => ({ requestAccessToken: () => config.callback({ access_token: "synthetic-ephemeral" }) }) } },
    picker: { PickerBuilder: class { constructor() { opened++; } } },
  } };
  try {
    await assert.rejects(openGoogleDrivePicker({ appId: "123", clientId: "client", developerKey: "synthetic",
      connection: { enabled: true, connected: true, oauthClientId: "client", pickerAppId: "123", providerAccountId: "account-one" } }), /misma cuenta/);
    assert.equal(opened, 0);
  } finally { globalThis.window = previous; }
});

test("Picker cancellation disposes its UI and ignores a late selected file", async (context) => {
  const previous = globalThis.window;
  let callback, disposed = 0, maximum;
  class Builder {
    setMaxItems(value) { maximum = value; return this; }
    setAppId() { return this; } setDeveloperKey() { return this; } setOAuthToken() { return this; }
    addView() { return this; } enableFeature() { return this; }
    setCallback(value) { callback = value; return this; }
    build() { return { setVisible() {}, dispose() { disposed++; } }; }
  }
  globalThis.window = { gapi: { load: (_, config) => config.callback() }, google: {
    accounts: { oauth2: { initTokenClient: (config) => ({ requestAccessToken: () => config.callback({ access_token: "synthetic-ephemeral" }) }) } },
    picker: { PickerBuilder: Builder, DocsView: class { setMode() { return this; } }, ViewId: { DOCS: "docs" }, DocsViewMode: { LIST: "list" },
      Feature: { MULTISELECT_ENABLED: "multi" }, Response: { ACTION: "action", DOCUMENTS: "docs" }, Action: { PICKED: "picked", CANCEL: "cancel" },
      Document: { ID: "id", NAME: "name", MIME_TYPE: "mime" } },
  } };
  context.mock.method(globalThis, "fetch", async () => ({ ok: true, json: async () => ({ user: { permissionId: "account-one" } }) }));
  const abort = new AbortController();
  try {
    const work = openGoogleDrivePicker({ appId: "123", clientId: "client", developerKey: "synthetic", signal: abort.signal,
      connection: { enabled: true, connected: true, oauthClientId: "client", pickerAppId: "123", providerAccountId: "account-one" } });
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(maximum, 25);
    abort.abort();
    await assert.rejects(work, { name: "AbortError" });
    assert.equal(disposed, 1);
    callback({ action: "picked", docs: [{ id: "late-file" }] });
    assert.equal(disposed, 1);
  } finally { globalThis.window = previous; }
});
