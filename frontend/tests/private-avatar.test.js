import assert from "node:assert/strict";
import test from "node:test";
import { getProfilePicture, uploadProfilePicture, removeProfilePicture } from "../src/features/profile/api/profile.api.js";
import { loadPrivateAvatar } from "../src/features/profile/api/private-avatar.js";

const path = "/api/v1/profile/avatar?version=7";
const tick = () => new Promise((resolve) => setImmediate(resolve));
const jpeg = () => ({ contentType: "image/jpeg", blob: new Blob(["synthetic"]) });

test("avatar mutations carry the profile version and return the updated profile", async () => {
  await uploadProfilePicture(async (url, options) => {
    assert.equal(url, "/api/v1/profile/upload");
    assert.equal(options.body.get("expected_version"), "7");
    assert.equal(options.body.get("file").size, 9);
    assert.equal(options.method, "POST");
  }, new Blob(["synthetic"]), 7);
  await removeProfilePicture(async (url, options) => {
    assert.equal(url, "/api/v1/profile/avatar");
    assert.equal(options.method, "DELETE");
    assert.deepEqual(JSON.parse(options.body), { expected_version: 8 });
  }, 8);
});

test("external and malformed references never reach the authenticated client", async () => {
  for (const url of ["https://other.invalid" + path, "//other.invalid/", "/static/a.jpg", path + "&owner=2", "/api/v1/profile/avatar?version=0"]) {
    await assert.rejects(getProfilePicture(() => assert.fail("token must stay local"), url));
  }
});

test("private download uses the authorized blob client without caching", async () => {
  const controller = new AbortController();
  await getProfilePicture(async (url, options) => {
    assert.equal(url, path);
    assert.equal(options.responseType, "blob");
    assert.equal(options.cache, "no-store");
    assert.equal(options.signal, controller.signal);
  }, path, controller.signal);
});

test("changing session aborts a pending avatar and suppresses its late response", async () => {
  let finish, signal;
  const dispose = loadPrivateAvatar((_, options) => {
    signal = options.signal;
    return new Promise((resolve) => { finish = resolve; });
  }, path, () => assert.fail("stale result"), { createObjectURL: () => assert.fail("stale blob") });
  await tick();
  dispose();
  assert.equal(signal.aborted, true);
  finish(jpeg());
  await tick();
});

test("a displayed object URL is revoked exactly once on cleanup", async () => {
  const revoked = [], states = [];
  const dispose = loadPrivateAvatar(async () => jpeg(), path, (state) => states.push(state), {
    createObjectURL: () => "blob:synthetic", revokeObjectURL: (url) => revoked.push(url),
  });
  await tick();
  assert.deepEqual(states, [{ src: "blob:synthetic", error: null }]);
  dispose(); dispose();
  assert.deepEqual(revoked, ["blob:synthetic"]);
});

test("invalid MIME, empty and oversized blobs do not become image URLs", async () => {
  for (const response of [{ ...jpeg(), contentType: "text/html" }, { ...jpeg(), blob: new Blob([]) },
    { ...jpeg(), blob: new Blob([new Uint8Array(1048577)]) }]) {
    const states = [];
    const dispose = loadPrivateAvatar(async () => response, path, (state) => states.push(state), {
      createObjectURL: () => assert.fail("invalid image"),
    });
    await tick();
    assert.equal(states.length, 1);
    assert.equal(states[0].src, null);
    assert.ok(states[0].error);
    dispose();
  }
});
