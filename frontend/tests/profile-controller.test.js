import assert from "node:assert/strict";
import test from "node:test";
import { createProfileController } from "../src/features/profile/model/profile-controller.js";

const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; };
const profile = (version = 1) => ({ version, email: "synthetic@example.com", additional_info: {} });

test("a disposed load cannot publish after the controller restarts", async () => {
  const old = deferred(), fresh = deferred(); let calls = 0, signal;
  const controller = createProfileController((_, options) => { signal = options.signal; return ++calls === 1 ? old.promise : fresh.promise; });
  const first = controller.start(); controller.dispose(); assert.equal(signal.aborted, true);
  const second = controller.start(); fresh.resolve(profile(2)); await second;
  old.resolve(profile(1)); await first;
  assert.equal(controller.getSnapshot().profile.version, 2);
});

test("save, upload, removal and reload share one in-flight guard", async () => {
  const pending = deferred(); let mutations = 0;
  const controller = createProfileController(async (_, options) => options.method === "GET" ? profile() : (mutations++, pending.promise));
  await controller.start();
  const saving = controller.save({ email: "changed@example.com" });
  assert.equal(await controller.save({}), false);
  assert.equal(await controller.uploadAvatar(new Blob(["synthetic"])), false);
  assert.equal(await controller.removeAvatar(), false);
  assert.equal(await controller.reload(), false);
  pending.resolve(profile(2)); await saving;
  assert.equal(mutations, 1);
});

test("avatar updates advance version without replacing the contact form snapshot", async () => {
  const calls = [];
  const controller = createProfileController(async (url, options) => {
    calls.push(options);
    return profile(calls.length);
  });
  await controller.start(); const snapshot = controller.getSnapshot().formProfile;
  await controller.uploadAvatar(new Blob(["synthetic"]));
  assert.equal(controller.getSnapshot().formProfile, snapshot);
  assert.equal(controller.getSnapshot().profile.version, 2);
  await controller.save({ email: "new@example.com" });
  assert.equal(JSON.parse(calls[2].body).expected_version, 2);
  assert.equal(controller.getSnapshot().formProfile.version, 3);
});

test("a conflict or network failure preserves the form until an explicit reload", async () => {
  let error = Object.assign(new Error("conflict"), { status: 409 });
  const controller = createProfileController(async (_, options) => { if (options.method === "GET") return profile(); throw error; });
  await controller.start(); const snapshot = controller.getSnapshot().formProfile;
  await controller.save({}); assert.equal(controller.getSnapshot().isConflict, true);
  assert.equal(controller.getSnapshot().formProfile, snapshot);
  error = new Error("offline"); await controller.save({});
  assert.equal(controller.getSnapshot().error, "offline"); assert.equal(controller.getSnapshot().formProfile, snapshot);
  await controller.reload(); assert.equal(controller.getSnapshot().error, null);
});

test("a late mutation cannot call the global setter or unlock a new write", async () => {
  const old = deferred(), fresh = deferred(); let writes = 0; const updated = [];
  const controller = createProfileController(async (_, options) => options.method === "GET" ? profile() : ++writes === 1 ? old.promise : fresh.promise,
    (data) => updated.push(data));
  await controller.start(); const first = controller.save({}); controller.dispose(); await controller.start();
  const second = controller.save({}); old.resolve(profile(99)); await first;
  assert.equal(controller.getSnapshot().isSaving, true); assert.deepEqual(updated, []);
  fresh.resolve(profile(2)); await second; assert.deepEqual(updated, [profile(2)]);
});

test("an older provider load cannot overwrite a profile confirmed by the editor", async () => {
  const pending = deferred(); const controller = createProfileController(() => pending.promise);
  const load = controller.start(); controller.acceptProfile(profile(8)); pending.resolve(profile(1)); await load;
  assert.equal(controller.getSnapshot().profile.version, 8);
  controller.acceptProfile(profile(7)); assert.equal(controller.getSnapshot().profile.version, 8);
});
