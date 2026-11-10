import assert from "node:assert/strict";
import test from "node:test";
import { assignDocument, listAssignedToMe, listManagedByMe, listNotifications } from "../src/features/document-access/api/document-access.api.ts";
import { ApiError, parseResponse } from "../src/shared/api/httpClient.ts";

for (const [loader, path, key, normalizedKey] of [
  [listAssignedToMe, "assigned-to-me", "assignment_id", "assignmentId"],
  [listManagedByMe, "managed-by-me", "assignment_id", "assignmentId"],
  [listNotifications, "notifications", "notification_id", "notificationId"],
]) {
  test(`${path} preserves pagination and normalizes items`, async () => {
    const client = async (url) => {
      assert.equal(url, `/api/v1/documents/${path}?limit=50&offset=50`);
      return { items: [{ [key]: "synthetic" }], limit: 50, offset: 50, has_more: true };
    };
    const page = await loader(client, 50);
    assert.equal(page.items[0][normalizedKey], "synthetic");
    assert.equal(page.hasMore, true);
    assert.equal(page.nextOffset, 51);
  });
}

test("empty final page ends pagination", async () => {
  assert.deepEqual(await listNotifications(async () => ({ items: [], offset: 0, has_more: false })), {
    items: [], hasMore: false, nextOffset: 0,
  });
});

test("assignment sends an explicit UTC due date", async () => {
  await assignDocument(async (url, options) => {
    assert.equal(url, "/api/v1/documents/synthetic/assignments");
    assert.equal(JSON.parse(options.body).due_at, "2030-01-02T13:30:00.000Z");
    return { assignment_id: "synthetic" };
  }, "synthetic", { userId: 42, dueAt: "2030-01-02T10:30:00-03:00" });
});

test("validation errors become readable text with status preserved", async () => {
  const response = Response.json({ detail: [{ loc: ["body", "metadata"], msg: "Metadata exceeds 16384 UTF-8 bytes." }] }, { status: 422 });
  await assert.rejects(parseResponse(response), (error) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.status, 422);
    assert.equal(error.message, "metadata: Metadata exceeds 16384 UTF-8 bytes.");
    return true;
  });
});

test("state conflicts retain their message and HTTP status", async () => {
  await assert.rejects(parseResponse(Response.json({ detail: "Assignment transition is not allowed." }, { status: 409 })), (error) => {
    assert.equal(error.message, "Assignment transition is not allowed.");
    assert.equal(error.status, 409);
    return true;
  });
});
