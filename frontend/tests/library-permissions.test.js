import assert from "node:assert/strict";
import test from "node:test";
import { listFolders } from "../src/features/document-library/api/document-library.api.ts";

for (const [count, expected] of [[0, 0], [2, 2], [undefined, 0]]) {
  test(`folder count ${count} does not inherit a historical metadata count`, async () => {
    const page = await listFolders(async () => ({ items: [{
      folder_id: "synthetic", document_count: count, metadata: { document_count: 99 },
    }], limit: 50, offset: 0, has_more: false }));
    assert.equal(page.items[0].documentCount, expected);
  });
}
