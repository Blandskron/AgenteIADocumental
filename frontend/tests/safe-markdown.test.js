import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";
import react from "@vitejs/plugin-react";

test("SafeMarkdown renders headings, lists, bold, code, clickable citations, and escapes XSS HTML", async () => {
  const server = await createServer({
    configFile: false,
    plugins: [react()],
    optimizeDeps: { noDiscovery: true, include: [] },
    server: { middlewareMode: true, hmr: false },
    appType: "custom",
  });
  try {
    const { SafeMarkdown } = await server.ssrLoadModule(
      "/src/features/chat/ui/SafeMarkdown.tsx",
    );
    const malicious = [
      "# Resumen",
      "",
      "El plazo es **45 dias** segun [Fuente 1] y codigo `ACTA-2026-014`.",
      "",
      "- Punto uno con <script>alert('xss')</script>",
      '- Punto dos con <svg onload="alert(1)"><foreignObject></foreignObject></svg>',
    ].join("\n");

    const html = renderToStaticMarkup(
      React.createElement(SafeMarkdown, {
        content: malicious,
        sourceCount: 2,
        onCitationClick: () => {},
      }),
    );

    assert.match(html, /<h3[^>]*>Resumen<\/h3>/);
    assert.match(html, /<strong>45 dias<\/strong>/);
    assert.match(html, /<code>ACTA-2026-014<\/code>/);
    assert.match(
      html,
      /<button[^>]*class="citation-chip"[^>]*>Fuente 1<\/button>/,
    );
    assert.doesNotMatch(html, /<script>/i);
    assert.doesNotMatch(html, /<svg/i);
    assert.match(html, /&lt;script&gt;/);
  } finally {
    await server.close();
  }
});
