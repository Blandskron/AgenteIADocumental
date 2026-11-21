import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import react from "@vitejs/plugin-react";
import { createServer } from "vite";

test("VerifiedVisualsPanel renders SVG graph and provenance-tagged metrics, CSV neutralizes formulas", async () => {
  const server = await createServer({
    configFile: false,
    plugins: [react()],
    server: { middlewareMode: true, hmr: false },
    appType: "custom",
  });
  try {
    const visualsMod = await server.ssrLoadModule(
      "/src/features/studio/VerifiedVisualsPanel.tsx",
    );
    const exportMod = await server.ssrLoadModule(
      "/src/features/studio/studioExport.ts",
    );

    const html = renderToStaticMarkup(
      React.createElement(visualsMod.VerifiedVisualsPanel),
    );
    assert.ok(html.includes("Grafo conceptual verificado"));
    assert.ok(html.includes("[doc-demo#0]"));

    const csv = exportMod.buildVerifiedEvidenceCsv([
      { label: "=HYPERLINK(\"http://evil\")", value: 42, provenance: "d1#0" },
    ]);
    assert.ok(csv.includes("'=HYPERLINK("));
    assert.ok(csv.includes("d1#0"));
  } finally {
    await server.close();
  }
});

