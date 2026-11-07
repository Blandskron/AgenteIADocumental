import assert from "node:assert/strict";
import test from "node:test";
import { getProfile, updateProfile } from "../src/features/profile/api/profile.api.js";

test("profile writes send the version last read and omit owner identifiers", async () => {
  const client = async (path, options) => {
    assert.equal(path, "/api/v1/profile");
    assert.equal(options.method, "PUT");
    const body = JSON.parse(options.body);
    assert.deepEqual(body, { expected_version: 7, email: null, additional_info: {} });
    return { version: 8 };
  };
  assert.deepEqual(await updateProfile(client, { email: null, additional_info: {}, user_id: "forbidden" }, 7), { version: 8 });
});

test("initial creation uses version zero and preserves explicit empty values", async () => {
  await updateProfile(async (_, options) => {
    assert.deepEqual(JSON.parse(options.body), { expected_version: 0, phone_number: "", profile_picture_url: null });
  }, { phone_number: "", profile_picture_url: null }, 0);
});

test("a conflict is propagated once without automatic overwrite or retry", async () => {
  let calls = 0;
  const error = Object.assign(new Error("conflict"), { status: 409 });
  await assert.rejects(updateProfile(async () => { calls++; throw error; }, { email: "synthetic@example.com" }, 1),
    (caught) => caught === error);
  assert.equal(calls, 1);
});

test("reading the profile preserves its server version", async () => {
  const result = await getProfile(async (path, options) => {
    assert.equal(path, "/api/v1/profile");
    assert.equal(options.method, "GET");
    assert.equal(options.cache, "no-store");
    return { version: 12 };
  });
  assert.equal(result.version, 12);
});
