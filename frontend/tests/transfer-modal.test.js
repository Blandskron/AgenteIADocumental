import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";
import react from "@vitejs/plugin-react";

test("transfer modal renders more than six rows, zero bytes and pagination controls", async () => {
  const server = await createServer({ configFile: false, plugins: [react()], optimizeDeps: { noDiscovery: true, include: [] },
    server: { middlewareMode: true }, appType: "custom" });
  try {
    const { TransferModal } = await server.ssrLoadModule("/src/shared/components/TransferModal/TransferModal.jsx");
    const html = renderToStaticMarkup(React.createElement(TransferModal, { isOpen: true, hasMore: true,
      transfers: Array.from({ length: 12 }, (_, index) => ({ transferId: String(index), filename: `synthetic-${index}.txt`, sizeBytes: 0, status: "RUNNING", progress: 65 })) }));
    assert.match(html, /synthetic-11.txt/); assert.match(html, /12 procesos cargados/);
    assert.match(html, /0 B/); assert.match(html, /Cargar más procesos/); assert.match(html, /conserva los activos/);
    const { TransferWarning } = await server.ssrLoadModule("/src/shared/components/TransferModal/TransferWarning.jsx");
    const warning = renderToStaticMarkup(React.createElement(TransferWarning, { warning: "No se pudo actualizar el historial" }));
    assert.match(warning, /role="status"/); assert.match(warning, /Cerrar aviso/);
  } finally { await server.close(); }
});
