import test from "node:test";
import assert from "node:assert/strict";
import { prepareImportAttempt, finishImportAttempt } from "../src/features/google-drive-import/import-attempt.ts";

const storage = () => { const entries = new Map(); return {
  getItem: (key) => entries.get(key) || null, setItem: (key, value) => entries.set(key, value),
}; };

test("lost response, refresh and page reload retain the same operation and connection snapshot", () => {
  const cache = storage(), input = { files: [{ fileId: "synthetic" }], metadata: {} };
  const first = prepareImportAttempt("owner-tenant", input, 1, cache, () => "operation-one");
  const reloaded = prepareImportAttempt("owner-tenant", input, 2, cache, () => "must-not-be-used");
  assert.equal(first.operationId, reloaded.operationId);
  assert.equal(reloaded.connectionVersion, 1);
  assert.throws(() => prepareImportAttempt("owner-tenant", { files: [{ fileId: "changed" }] }, 2, cache), /sin resultado confirmado/);
});

test("ambiguous upload retains its key; other selections get their own operation", () => {
  const cache = storage(), input = { files: [{ fileId: "synthetic" }] };
  prepareImportAttempt("owner", input, 1, cache, () => "operation-one");
  finishImportAttempt("owner", "operation-one", { status: "REVIEW_REQUIRED" }, cache);
  assert.equal(prepareImportAttempt("owner", input, 2, cache).operationId, "operation-one");
  finishImportAttempt("owner", "operation-one", { status: "COMPLETED" }, cache);
  assert.equal(prepareImportAttempt("owner", { files: [{ fileId: "different" }] }, 2, cache, () => "operation-two").operationId, "operation-two");
});

test("accounts and tenants cannot inherit another operation", () => {
  const cache = storage(), input = { files: [{ fileId: "synthetic" }] };
  const first = prepareImportAttempt("owner-tenant-one", input, 1, cache, () => "one");
  const other = prepareImportAttempt("owner-tenant-two", input, 1, cache, () => "two");
  assert.notEqual(first.operationId, other.operationId);
});

test("a known failure can start a fresh attempt while successful or uncertain uploads retain their key", () => {
  const cache = storage(), input = { files: [{ fileId: "synthetic" }] };
  prepareImportAttempt("owner", input, 1, cache, () => "one");
  finishImportAttempt("owner", "one", { status: "FAILED" }, cache);
  assert.equal(prepareImportAttempt("owner", input, 2, cache, () => "two").operationId, "two");
});
