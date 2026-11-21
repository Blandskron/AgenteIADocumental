import assert from "node:assert/strict";
import test from "node:test";

import {
  exportStudioCsv,
  listStudioTemplates,
  validateStudioMermaid,
} from "../src/features/studio/api/studio.api.ts";

test("studio API client targets expected Knowledge Studio endpoints", async () => {
  const calls = [];
  const client = async (path, options) => {
    calls.push({ path, options });
    if (path.endsWith("/templates")) return { templates: ["summary.executive"] };
    if (path.endsWith("/mermaid/validate")) return { status: "ok", source: "flowchart LR" };
    return { csv: "col,verified,provenance\n" };
  };

  const tpls = await listStudioTemplates(client);
  assert.deepEqual(tpls.templates, ["summary.executive"]);

  const mermaid = await validateStudioMermaid(client, "flowchart LR");
  assert.equal(mermaid.status, "ok");

  const csv = await exportStudioCsv(client, { template_id: "evidence_table", title: "T" });
  assert.match(csv.csv, /provenance/);
  assert.equal(calls.length, 3);
});

