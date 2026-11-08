import test from "node:test";
import assert from "node:assert/strict";
import { openGoogleDrivePicker } from "../src/features/google-drive-import/google-picker.js";

test("Picker rejects a different OAuth client before loading Google scripts", async () => {
  await assert.rejects(openGoogleDrivePicker({ appId: "123", clientId: "different", developerKey: "synthetic",
    connection: { connected: true, oauthClientId: "expected", pickerAppId: "123", providerAccountId: "account-one" } }), /aplicación y cuenta/);
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
      connection: { connected: true, oauthClientId: "client", pickerAppId: "123", providerAccountId: "account-one" } }), /misma cuenta/);
    assert.equal(opened, 0);
  } finally { globalThis.window = previous; }
});
