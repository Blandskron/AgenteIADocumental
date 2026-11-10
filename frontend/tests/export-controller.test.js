import assert from "node:assert/strict";
import test from "node:test";
import { createExportController } from "../src/features/document-export/export-controller.ts";
import { savePdf } from "../src/features/document-export/download-pdf.ts";
import { listExports } from "../src/features/document-export/api/document-export.api.ts";
import { createSessionClient } from "../src/shared/api/session-client.ts";

const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; };
const row = (id) => ({ export_id: id, filename: `${id}.pdf`, title: id, status: "COMPLETED", file_size_bytes: 30 });
const file = () => ({ blob: new Blob(["%PDF-synthetic"], { type: "application/pdf" }), contentType: "application/pdf" });
const payload = { answer: "Synthetic", conversationId: "remote" };

test("pagination deduplicates, coalesces load more and refresh invalidates old pages", async () => {
  const pending = deferred(); let reads = 0;
  const controller = createExportController(async () => {
    reads++;
    if (reads === 1) return { items: [row("one")], next_cursor: "next" };
    if (reads === 2) return pending.promise;
    return { items: [row("new")], next_cursor: null };
  });
  controller.start(); await controller.refresh();
  const old = controller.loadMore(); await controller.loadMore();
  assert.equal(reads, 2);
  await controller.refresh(); pending.resolve({ items: [row("old")], next_cursor: null }); await old;
  assert.deepEqual(controller.getSnapshot().items.map((item) => item.exportId), ["new"]);
  controller.dispose();
});

test("append failure preserves rows and nonadvancing cursor fails visibly", async () => {
  let reads = 0;
  const controller = createExportController(async () => {
    if (++reads === 1) return { items: [row("one")], next_cursor: "next" };
    if (reads === 2) throw new Error("Read failed");
    return { items: [], next_cursor: "next" };
  });
  controller.start(); await controller.refresh(); await controller.loadMore();
  assert.equal(controller.getSnapshot().items.length, 1);
  assert.match(controller.getSnapshot().error, /Read failed/);
  await controller.loadMore(); assert.match(controller.getSnapshot().error, /no avanzó/);
  controller.dispose();
});

test("double submission coalesces and network retry retains operation UUID", async () => {
  const pending = deferred(); const keys = []; let saved = 0;
  const controller = createExportController(async (path, options) => {
    if (options.method === "POST") { keys.push(options.headers["Idempotency-Key"]); return keys.length === 1 ? pending.promise : row("one"); }
    return file();
  }, { uuid: () => "same-operation", save: async () => { saved++; return true; } });
  controller.start(); const first = controller.exportMessage("message", payload);
  assert.equal(await controller.exportMessage("message", payload), false);
  pending.reject(new Error("Lost response")); await first;
  assert.equal(await controller.exportMessage("message", payload), true);
  assert.deepEqual(keys, ["same-operation", "same-operation"]); assert.equal(saved, 1);
  controller.dispose();
});

test("download failure retries saved PDF without creating a second one", async () => {
  let creates = 0, downloads = 0;
  const controller = createExportController(async (_, options) => {
    if (options.method === "POST") { creates++; return row("one"); }
    if (++downloads === 1) throw new Error("Download failed");
    return file();
  }, { uuid: () => "operation", save: async () => true });
  controller.start(); await controller.exportMessage("message", payload); await controller.exportMessage("message", payload);
  assert.equal(creates, 1); assert.equal(downloads, 2); controller.dispose();
});

test("disposed and earlier generations cannot download, publish or unlock a newer write", async () => {
  const old = deferred(), next = deferred(); let creates = 0, saves = 0;
  const controller = createExportController(async (_, options) => options.method === "POST" ? (++creates === 1 ? old.promise : next.promise) : file(),
    { uuid: () => String(creates), save: async () => { saves++; return true; } });
  controller.start(); const first = controller.exportMessage("old", payload);
  controller.dispose(); controller.start(); const second = controller.exportMessage("new", { answer: "New" });
  old.resolve(row("old")); await first;
  assert.equal(saves, 0); assert.equal(controller.getSnapshot().messageKey, "new");
  next.resolve(row("new")); await second; assert.equal(saves, 1); controller.dispose();
  assert.equal(await controller.exportMessage("ignored", payload), false);
});

test("cancel aborts the request and late PDF cannot reach browser", async () => {
  const pending = deferred(); let signal, saves = 0;
  const controller = createExportController(async (_, options) => { signal = options.signal; return pending.promise; },
    { uuid: () => "one", save: async () => { saves++; return true; } });
  controller.start(); const operation = controller.exportMessage("one", payload);
  controller.cancelPending(); assert.equal(signal.aborted, true);
  pending.resolve(row("one")); await operation;
  assert.equal(saves, 0); assert.equal(controller.getSnapshot().busyKey, ""); controller.dispose();
});

for (const status of [409, 410, 413]) test(`PDF status ${status} remains actionable`, async () => {
  const controller = createExportController(async () => { throw Object.assign(new Error("HTTP"), { status }); });
  controller.start(); await controller.download({ exportId: "one" });
  assert.ok(controller.getSnapshot().error.length > 10); assert.equal(controller.getSnapshot().busyKey, ""); controller.dispose();
});

test("API page rejects arrays, malformed IDs and empty cursors", async () => {
  for (const response of [[], { items: [{ export_id: "../outside" }], next_cursor: null }, { items: [], next_cursor: "" }]) {
    await assert.rejects(listExports(async () => response));
  }
});

test("object URLs are revoked even when clicking or removing the anchor fails", async () => {
  for (const point of ["click", "remove", "append"]) {
    let revoked = 0;
    const link = { click() { if (point === "click") throw new Error(point); }, remove() { if (point === "remove") throw new Error(point); } };
    const browser = { URL: { createObjectURL: () => "blob:synthetic", revokeObjectURL: () => revoked++ },
      document: { createElement: () => link, body: { appendChild() { if (point === "append") throw new Error(point); } } } };
    await assert.rejects(savePdf(file(), "safe.pdf", () => true, browser)); assert.equal(revoked, 1);
  }
});

test("invalid MIME/signature and stale session create no object URL", async () => {
  const browser = { URL: { createObjectURL: () => assert.fail("Unexpected URL") } };
  await assert.rejects(savePdf({ ...file(), contentType: "text/html" }, "safe.pdf", () => true, browser));
  await assert.rejects(savePdf({ ...file(), blob: new Blob(["HTML"]) }, "safe.pdf", () => true, browser));
  assert.equal(await savePdf(file(), "safe.pdf", () => false, browser), false);
});

test("account or tenant switch suppresses a valid late PDF before controller disposal", async () => {
  const original = global.fetch, pending = deferred(); let saves = 0;
  let session = { key: "old-tenant", auth: { access: "old" }, logout: () => assert.fail("Stale logout"),
    refreshAccessToken: () => assert.fail("Stale refresh") };
  global.fetch = () => pending.promise;
  try {
    const client = createSessionClient("https://synthetic.invalid", "old-tenant", () => session);
    const controller = createExportController(client, { save: async () => { saves++; return true; } });
    controller.start(); const download = controller.download({ exportId: "one", filename: "one.pdf" });
    session = { ...session, key: "new-tenant" };
    pending.resolve(new Response("%PDF-synthetic", { headers: { "Content-Type": "application/pdf" } }));
    assert.equal(await download, false); assert.equal(saves, 0); controller.dispose();
  } finally { global.fetch = original; }
});
