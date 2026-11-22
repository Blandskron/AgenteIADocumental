import assert from "node:assert/strict";
import test from "node:test";
import { fileURLToPath, URL } from "node:url";
import { createServer } from "vite";
import react from "@vitejs/plugin-react";

test("applySm2Offline advances intervals cleanly without network or telemetry", async () => {
  const server = await createServer({
    configFile: false,
    plugins: [react()],
    resolve: {
      alias: { "@": fileURLToPath(new URL("../src", import.meta.url)) },
    },
    optimizeDeps: { noDiscovery: true, include: [] },
    server: { middlewareMode: true, hmr: false },
    appType: "custom",
  });
  try {
    const { applySm2Offline } = await server.ssrLoadModule(
      "/src/features/studio/OfflineFlashcardDeck.tsx",
    );
    const base = {
      id: "c1",
      front: "Q",
      back: "A",
      repetitions: 0,
      intervalDays: 1,
      easeFactor: 2.5,
    };
    const r1 = applySm2Offline(base, 5);
    assert.equal(r1.repetitions, 1);
    assert.equal(r1.intervalDays, 1);
    const r2 = applySm2Offline(r1, 5);
    assert.equal(r2.repetitions, 2);
    assert.equal(r2.intervalDays, 6);
    const rFail = applySm2Offline(r2, 1);
    assert.equal(rFail.repetitions, 0);
    assert.equal(rFail.intervalDays, 1);
  } finally {
    await server.close();
  }
});

