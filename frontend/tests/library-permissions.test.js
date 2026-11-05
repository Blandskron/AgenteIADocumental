import assert from "node:assert/strict";
import test from "node:test";
import { listFolders } from "../src/features/document-library/api/document-library.api.js";

for (const [count, expected] of [[0, 0], [2, 2], [undefined, 0]]) {
  test(`folder count ${count} does not inherit a historical metadata count`, async () => {
    const folders = await listFolders(async () => [{
      folder_id: "synthetic", document_count: count, metadata: { document_count: 99 },
    }]);
    assert.equal(folders[0].documentCount, expected);
  });
}
