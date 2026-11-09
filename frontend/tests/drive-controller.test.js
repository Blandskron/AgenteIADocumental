import test from "node:test";
import assert from "node:assert/strict";
import { createDriveController } from "../src/features/google-drive-import/drive-controller.js";
import { listGoogleDriveImports, listGoogleDriveImportFiles } from "../src/features/google-drive-import/api/google-drive-import.api.js";

const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; };
function fixture() {
  let identity = {}, writes = 0, finished = 0, rejected = 0, signal;
  const pending = deferred(), states = [];
  const controller = createDriveController({ client: {}, scope: "synthetic", context: () => identity,
    changed: (state) => states.push(state), prepare: () => ({ operationId: "stable", connectionVersion: 2 }),
    finish: () => finished++, reject: () => rejected++, upload: (_, options) => { writes++; signal = options.signal; return pending.promise; } });
  return { controller, pending, states, switch: () => { identity = {}; }, get writes() { return writes; },
    get finished() { return finished; }, get rejected() { return rejected; }, get signal() { return signal; } };
}
const input = { files: [{ fileId: "synthetic-file" }] };
test("Drive has one lane for double submit and Picker; completes once", async () => {
  const f = fixture(); let completed = 0, picked = 0;
  const first = f.controller.import(input, 2, () => completed++);
  await f.controller.import(input, 2);
  await f.controller.picker(() => { picked++; }, () => {});
  assert.equal(f.writes, 1); assert.equal(picked, 0);
  f.pending.resolve({ status: "COMPLETED" }); await first;
  assert.equal(f.finished, 1); assert.equal(completed, 1); assert.equal(f.states.at(-1).busy, false);
});
for (const mode of ["cancel", "stop", "switch"]) test(`Drive ${mode} discards a late server result without completing its pending key`, async () => {
  const f = fixture(); let completed = 0;
  const work = f.controller.import(input, 2, () => completed++);
  if (mode === "switch") f.switch(); else f.controller[mode]();
  if (mode !== "switch") assert.equal(f.signal.aborted, true);
  const count = f.states.length;
  f.pending.resolve({ status: "COMPLETED" }); await work;
  assert.equal(f.finished, 0); assert.equal(completed, 0); assert.equal(f.states.length, count);
});
test("Drive ignores an earlier Picker failure and preserves ambiguous upload operation", async () => {
  const f = fixture(), picker = deferred();
  const work = f.controller.picker(() => picker.promise, () => assert.fail("late picker"));
  f.controller.cancel(); const count = f.states.length;
  picker.reject(new Error("late")); await work;
  assert.equal(f.states.length, count);
  const upload = f.controller.import(input, 2);
  f.pending.reject(new Error("network response lost")); await upload;
  assert.equal(f.finished, 0); assert.equal(f.rejected, 1);
  assert.match(f.states.at(-2).error, /lost/);
});
test("Drive file validation rejects duplicate/oversized batches before network", async () => {
  const f = fixture();
  await f.controller.import({ files: [...input.files, ...input.files] }, 2);
  await f.controller.import({ files: Array.from({ length: 26 }, (_, i) => ({ fileId: `file-${i}` })) }, 2);
  assert.equal(f.writes, 0);
});
test("Drive pages encode opaque IDs/cursors and reject legacy/malformed responses", async () => {
  let path;
  const api = async (url) => { path = url; return { items: [{ import_file_id: "f", import_id: "a/b" }], next_cursor: null }; };
  const result = await listGoogleDriveImportFiles(api, "a/b", { cursor: "abc" });
  assert.match(path, /a%2Fb\/files\?limit=25&after=abc/); assert.equal(result.items[0].importFileId, "f");
  for (const body of [[], {}, { items: [{}], next_cursor: null }, { items: [], next_cursor: "" }, { items: [], next_cursor: "abc" }]) {
    await assert.rejects(listGoogleDriveImports(async () => body), /inválida/);
  }
});
