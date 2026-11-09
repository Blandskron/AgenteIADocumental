import assert from "node:assert/strict";
import test from "node:test";
import { importGoogleDriveFiles } from "../src/features/google-drive-import/api/google-drive-import.api.js";
import { getImportWarning } from "../src/features/google-drive-import/import-result.js";

test("partial folder association preserves the imported document and its warning", async () => {
  const result = await importGoogleDriveFiles(async () => ({
    status: "PARTIAL", processed_files: 1, failed_files: 0, error_message: "Asociación incompleta",
    files: [{ status: "COMPLETED", document_id: "synthetic", error_message: "Sin carpeta",
      metadata: { folder_association: { status: "FAILED" } } }],
  }), { operationId: "synthetic-operation", files: [{ fileId: "synthetic" }], folderId: "synthetic-folder" });
  assert.equal(getImportWarning(result), "Asociación incompleta");
  assert.equal(result.files[0].documentId, "synthetic");
  assert.equal(result.files[0].errorMessage, "Sin carpeta");
});

test("complete imports have no warning", () => {
  assert.equal(getImportWarning({ status: "COMPLETED" }), "");
});

for (const status of ["PARTIAL", "FAILED"]) {
  test(`${status} without a summary has a visible fallback`, () => {
    assert.match(getImportWarning({ status }), /Revisa los documentos importados antes de reintentar/);
  });
}
