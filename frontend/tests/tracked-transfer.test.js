import assert from "node:assert/strict";
import test from "node:test";
import { runDocumentUpload, runDocumentDownload } from "../src/features/transfers/document-transfer-flows.js";
import { createTransferController } from "../src/features/transfers/transfer-controller.js";

const settle = () => new Promise((resolve) => setImmediate(resolve));
const pending = () => { let resolve; const promise = new Promise((done) => { resolve = done; }); return { promise, resolve }; };
const file = { name: "synthetic.txt", size: 0 };
const document = { documentId: "synthetic", filename: file.name, status: "PROCESSED" };

for (const kind of ["upload", "chat", "download"]) {
  for (const failure of ["create", "patch", "hang"]) {
    test(`${kind} completes once when journal ${failure} fails or stalls`, async () => {
      const journal = pending(); let files = 0, posts = 0, patches = 0;
      const controller = createTransferController(async (_path, options) => {
        if (options.method === "GET") return { items: [], offset: 0, limit: 50, has_more: false };
        if (options.method === "POST") {
          posts++;
          if (failure === "create") throw new Error("journal create failed");
          if (failure === "hang") return journal.promise;
          return { transfer_id: "event" };
        }
        patches++; throw new Error("journal patch failed");
      });
      controller.start(false);
      const operation = async () => { files++; return document; };
      const result = kind === "download"
        ? await runDocumentDownload({ transfers: controller, document, download: operation })
        : await runDocumentUpload({ transfers: controller, file, ...(kind === "chat" ? { conversationId: "session" } : {}),
          upload: operation, poll: () => assert.fail("Already processed"), isProcessed: () => true });
      assert.equal(result, document); assert.equal(files, 1);
      await settle();
      if (failure === "hang") { assert.equal(patches, 0); journal.resolve({ transfer_id: "event" }); await settle(); }
      assert.equal(posts, 1); assert.match(controller.getSnapshot().warning, /historial/);
      assert.equal(files, 1);
    });
  }
}

for (const kind of ["upload", "chat", "download"]) test(`${kind} error identity survives a failed FAILED update, with no file retry`, async () => {
  const original = new Error("original document error"); let files = 0;
  const controller = createTransferController(async (_path, options) => {
    if (options.method === "GET") return { items: [], offset: 0, limit: 50, has_more: false };
    if (options.method === "POST") return { transfer_id: "event" };
    throw new Error("history failure");
  });
  controller.start(false);
  const fail = async () => { files++; throw original; };
  const promise = kind === "download" ? runDocumentDownload({ transfers: controller, document, download: fail })
    : runDocumentUpload({ transfers: controller, file, conversationId: kind === "chat" ? "session" : undefined, upload: fail, isProcessed: () => true });
  await assert.rejects(promise,
    (error) => error === original);
  await settle(); assert.equal(files, 1); assert.match(controller.getSnapshot().warning, /history failure/);
});

test("chat stages remain ordered after slow journal creation and conserve conversation metadata", async () => {
  const creation = pending(); const writes = [];
  const controller = createTransferController(async (_path, options) => {
    if (options.method === "GET") return { items: [], offset: 0, limit: 50, has_more: false };
    writes.push(JSON.parse(options.body));
    if (options.method === "POST") return creation.promise;
    return { transfer_id: "event" };
  });
  controller.start(false);
  assert.equal(await runDocumentUpload({ transfers: controller, file, conversationId: "session",
    upload: async () => ({ ...document, status: "PENDING" }), poll: async () => document, isProcessed: () => false }), document);
  creation.resolve({ transfer_id: "event" }); await settle();
  assert.deepEqual(writes.map((write) => write.progress), [15, 65, 100]);
  assert.equal(writes[0].metadata.conversation_id, "session");
});

test("disposal cancels queued journal steps and warnings after a file already started", async () => {
  const creation = pending(); let calls = 0;
  const controller = createTransferController(async () => { calls++; return creation.promise; });
  controller.start(false);
  await runDocumentDownload({ transfers: controller, document, download: async () => document });
  controller.dispose(); controller.start(false);
  creation.resolve({ transfer_id: "old" }); await settle();
  assert.equal(calls, 1); assert.equal(controller.getSnapshot().warning, "");
});

for (const original of [null, "synthetic non-Error"]) test(`non-Error rejection remains unchanged: ${String(original)}`, async () => {
  const controller = createTransferController(async (_path, options) => {
    if (options.method === "POST") return { transfer_id: "event" };
    if (options.method === "GET") return { items: [], offset: 0, limit: 50, has_more: false };
    throw null;
  });
  controller.start(false);
  let caught = false;
  try { await runDocumentDownload({ transfers: controller, document, download: async () => { throw original; } }); }
  catch (error) { caught = true; assert.equal(error, original); }
  assert.equal(caught, true); await settle(); assert.match(controller.getSnapshot().warning, /historial/);
});
