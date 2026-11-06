import assert from "node:assert/strict";
import test from "node:test";

import { createTransfer, listTransfers, updateTransfer } from "../src/features/transfers/api/transfers.api.js";

test("transfer metadata from upload and failure flows survives the API round trip", async () => {
  const requests = [];
  const apiClient = async (path, options) => {
    const payload = JSON.parse(options.body);
    requests.push({ path, payload });
    return { transfer_id: "synthetic", owner_user_id: "42", ...payload };
  };
  const metadata = { conversation_id: null, error: "Error sintético", nested: [1, true, "ñ"] };
  const created = await createTransfer(apiClient, {
    filename: "sintético.txt", direction: "UPLOAD", status: "RUNNING", progress: 15,
    size_bytes: 0, metadata,
  });
  assert.deepEqual(created.metadata, metadata);
  assert.equal(created.sizeBytes, 0);
  assert.equal(created.progress, 15);
  const updated = await updateTransfer(apiClient, "synthetic", {
    status: "FAILED", progress: 15, metadata: { conversation_id: "session", error: "Error sintético" },
  });
  assert.deepEqual(updated.metadata, { conversation_id: "session", error: "Error sintético" });
  assert.deepEqual(requests[0].payload.metadata, metadata);
  assert.equal(requests[1].path, "/api/v1/transfers/synthetic");
});

test("PATCH preserves explicit nulls and empty metadata and leaves omitted fields absent", async () => {
  const apiClient = async (_path, options) => {
    const payload = JSON.parse(options.body);
    assert.deepEqual(payload, { document_id: null, size_bytes: null, metadata: {} });
    assert.equal(Object.hasOwn(payload, "progress"), false);
    return { transfer_id: "synthetic", ...payload };
  };
  const result = await updateTransfer(apiClient, "synthetic", { document_id: null, size_bytes: null, metadata: {} });
  assert.equal(result.documentId, null);
  assert.equal(result.sizeBytes, null);
  assert.deepEqual(result.metadata, {});
});

test("list keeps metadata and rejected writes preserve the original API error", async () => {
  const rows = await listTransfers(async () => [{ transfer_id: "synthetic", metadata: { conversation_id: "session" }, size_bytes: 0 }]);
  assert.deepEqual(rows[0].metadata, { conversation_id: "session" });
  assert.equal(rows[0].sizeBytes, 0);
  const original = new Error("Invalid request value.");
  await assert.rejects(createTransfer(async () => { throw original; }, {}), (error) => error === original);
  await assert.rejects(updateTransfer(async () => { throw original; }, "synthetic", {}), (error) => error === original);
});
