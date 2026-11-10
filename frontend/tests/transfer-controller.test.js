import assert from "node:assert/strict";
import test from "node:test";
import { createTransferController } from "../src/features/transfers/transfer-controller.ts";
import { listTransfers, updateTransfer } from "../src/features/transfers/api/transfers.api.ts";

const page = (ids, offset = 0, more = false) => ({ items: ids.map((id) => ({ transfer_id: id, status: "RUNNING" })), limit: 50, offset, has_more: more });
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };
const settle = () => new Promise((resolve) => setImmediate(resolve));

test("pages append beyond six and advance by raw size while deduplicating", async () => {
  const paths = [];
  const controller = createTransferController(async (path) => {
    paths.push(path);
    return paths.length === 1 ? page(Array.from({ length: 50 }, (_, i) => String(i)), 0, true) : page(["49", "50"], 50);
  });
  controller.start(false);
  await controller.refreshTransfers(); await controller.loadMore();
  assert.equal(controller.getSnapshot().transfers.length, 51);
  assert.equal(controller.getSnapshot().nextOffset, 52);
  assert.equal(controller.getSnapshot().hasMore, false);
  assert.equal(paths[1], "/api/v1/transfers?limit=50&offset=50");
});

test("old append and previous mounts cannot replace a refresh", async () => {
  const pending = deferred(); let calls = 0;
  const controller = createTransferController(async () => (++calls === 1 ? page(["first"], 0, true) : calls === 2 ? pending.promise : page(["fresh"])));
  controller.start(false); await controller.refreshTransfers();
  const old = controller.loadMore();
  await controller.refreshTransfers();
  pending.resolve(page(["old"], 1)); await old;
  assert.deepEqual(controller.getSnapshot().transfers.map((row) => row.transferId), ["fresh"]);
  const journal = controller.captureJournal(); controller.dispose(); controller.start(false);
  assert.equal(journal.isActive(), false);
  await journal.recordTransfer({});
  assert.equal(calls, 3);
});

test("duplicate pagination clicks coalesce and failures keep previous rows", async () => {
  const pending = deferred(); let calls = 0;
  const controller = createTransferController(async () => (++calls === 1 ? page(["keep"], 0, true) : pending.promise));
  controller.start(false); await controller.refreshTransfers();
  const one = controller.loadMore(); await controller.loadMore();
  assert.equal(calls, 2);
  pending.reject(new Error("synthetic failure")); await one;
  assert.equal(controller.getSnapshot().transfers[0].transferId, "keep");
  assert.equal(controller.getSnapshot().error, "synthetic failure");
});

test("clear refreshes active rows, catches errors, and prevents duplicate requests", async () => {
  const pending = deferred(); let deletes = 0, loads = 0;
  const controller = createTransferController(async (_path, options) => {
    if (options.method === "DELETE") { deletes++; return pending.promise; }
    loads++; return page(["active"]);
  });
  controller.start(false); await controller.refreshTransfers();
  const one = controller.clearHistory(); await controller.clearHistory();
  assert.equal(deletes, 1);
  pending.resolve({ count: 1000 }); await one;
  assert.equal(loads, 2);
  assert.equal(controller.getSnapshot().transfers[0].transferId, "active");
  const broken = createTransferController(async () => { throw new Error("clear failed"); });
  broken.start(false); assert.equal(await broken.clearHistory(), false);
  assert.equal(broken.getSnapshot().error, "clear failed");
});

test("late writes and clears cannot publish warnings or invoke another request after disposal", async () => {
  const pending = deferred(); let calls = 0;
  const controller = createTransferController(async () => { calls++; return pending.promise; });
  controller.start(false);
  const journal = controller.captureJournal(); const write = journal.recordTransfer({});
  controller.dispose(); controller.start(false);
  pending.resolve({ transfer_id: "old" }); await write; await settle();
  journal.noteWarning(new Error("old")); await journal.patchTransfer("old", {});
  assert.equal(calls, 1); assert.equal(controller.getSnapshot().warning, "");
  assert.deepEqual(controller.getSnapshot().transfers, []);
});

test("array contracts fail visibly and identifiers are encoded", async () => {
  await assert.rejects(listTransfers(async () => []), /incompatible/);
  await updateTransfer(async (path) => { assert.equal(path, "/api/v1/transfers/a%2Fb%3F"); return { transfer_id: "a/b?" }; }, "a/b?", { progress: 50 });
});

test("malformed page offsets and items fail visibly", async () => {
  for (const payload of [{ ...page([]), offset: 1 }, { ...page([]), limit: 1 }, { ...page([]), items: [{}] }]) {
    await assert.rejects(listTransfers(async () => payload), /incompatible/);
  }
});

test("late clear cannot refresh a restarted or different client", async () => {
  const pending = deferred(); let calls = 0;
  const controller = createTransferController(async () => { calls++; return pending.promise; });
  controller.start(false); const clearing = controller.clearHistory();
  controller.dispose(); controller.start(false);
  pending.resolve({ count: 1 }); await clearing;
  assert.equal(calls, 1); assert.equal(controller.getSnapshot().isClearing, false);
});

test("successful clear retains active cached rows when its reload fails", async () => {
  let loads = 0;
  const controller = createTransferController(async (_path, options) => {
    if (options.method === "DELETE") return { count: 1 };
    if (++loads === 1) return page(["active"]);
    throw new Error("reload failed");
  });
  controller.start(false); await controller.refreshTransfers();
  assert.equal(await controller.clearHistory(), false);
  assert.equal(controller.getSnapshot().transfers[0].transferId, "active");
  assert.equal(controller.getSnapshot().error, "reload failed");
});
