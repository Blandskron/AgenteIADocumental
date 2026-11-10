import assert from "node:assert/strict";
import test from "node:test";
import { createLibraryController } from "../src/features/document-library/library-controller.ts";
import { listFolders, listFolderDocuments, listRecentDocuments } from "../src/features/document-library/api/document-library.api.ts";
import { createSearchController } from "../src/features/document-search/search-controller.ts";

const page = (items = [], offset = 0, has_more = false) => ({ items, offset, limit: 50, has_more });
const doc = (id) => ({ document_id: id, filename: `${id}.txt` });
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };
const emptyApi = async (path) => path === "/api/v1/library/markers" ? [] : page();

test("all list adapters preserve pages and encode identifiers", async () => {
  const requests = [];
  const api = async (path) => { requests.push(path); return page([doc("a")], 50, true); };
  assert.deepEqual(await listRecentDocuments(api, { offset: 50 }), {
    items: [{ documentId: "a", filename: "a.txt", mimeType: "", status: "UNKNOWN", chunkCount: 0, updatedAt: "", isFavorite: false }],
    offset: 50, limit: 50, hasMore: true,
  });
  await listFolderDocuments(api, "folder?part", { offset: 50 });
  assert.match(requests[1], /folder%3Fpart\/documents\?limit=50&offset=50/);
});

test("legacy array contracts fail visibly instead of producing an empty library", async () => {
  await assert.rejects(listFolders(async () => []), /incompatible/);
});

test("load more appends, deduplicates and advances by raw page size; empty page terminates", async () => {
  const offsets = [];
  const controller = createLibraryController(async (path) => {
    if (!path.includes("/recent?")) return emptyApi(path);
    const offset = Number(new URL(path, "https://synthetic.invalid").searchParams.get("offset"));
    offsets.push(offset);
    return offset === 0 ? page([doc("a"), doc("b")], 0, true) : offset === 2 ? page([doc("b"), doc("c")], 2, true) : page([], 4);
  });
  await controller.start();
  await controller.loadMore("recent");
  assert.deepEqual(controller.getSnapshot().recent.items.map((d) => d.documentId), ["a", "b", "c"]);
  await controller.loadMore("recent");
  assert.equal(controller.getSnapshot().recent.hasMore, false);
  await controller.loadMore("recent");
  assert.deepEqual(offsets, [0, 2, 4]);
});

test("double pagination clicks issue one request and retain previous items on failure", async () => {
  const waiting = deferred();
  let pages = 0;
  const controller = createLibraryController(async (path) => {
    if (!path.includes("/recent?")) return emptyApi(path);
    pages += 1;
    return pages === 1 ? page([doc("a")], 0, true) : waiting.promise;
  });
  await controller.start();
  const pending = controller.loadMore("recent");
  await controller.loadMore("recent");
  assert.equal(pages, 2);
  waiting.reject(new Error("Synthetic unavailable"));
  await pending;
  assert.equal(controller.getSnapshot().recent.items[0].documentId, "a");
  assert.equal(controller.getSnapshot().recent.error, "Synthetic unavailable");
  assert.equal(controller.getSnapshot().recent.loading, false);
});

test("refresh discards an older page response and clears revoked cached rows", async () => {
  const waiting = deferred();
  let calls = 0;
  const controller = createLibraryController(async (path) => {
    if (!path.includes("/recent?")) return emptyApi(path);
    calls += 1;
    return calls === 1 ? page([doc("revoked")], 0, true) : calls === 2 ? waiting.promise : page([doc("fresh")]);
  });
  await controller.start();
  const stale = controller.loadMore("recent");
  await controller.refreshLibrary();
  waiting.resolve(page([doc("stale")], 1));
  await stale;
  assert.deepEqual(controller.getSnapshot().recent.items.map((d) => d.documentId), ["fresh"]);
});

test("opening another folder and closing it invalidate late results", async () => {
  const slow = deferred(), next = deferred();
  const controller = createLibraryController(async (path) => path.includes("/folders/a/") ? slow.promise : next.promise);
  const first = controller.openFolder({ folderId: "a" });
  const second = controller.openFolder({ folderId: "b" });
  next.resolve(page([doc("b")]));
  await second;
  slow.resolve(page([doc("a")]));
  await first;
  assert.equal(controller.getSnapshot().selectedFolder.folderId, "b");
  assert.equal(controller.getSnapshot().content.items[0].documentId, "b");
  const closing = deferred();
  const other = createLibraryController(async () => closing.promise);
  const pending = other.openFolder({ folderId: "c" });
  other.closeFolder();
  closing.resolve(page([doc("late")]));
  await pending;
  assert.equal(other.getSnapshot().selectedFolder, null);
  assert.deepEqual(other.getSnapshot().content.items, []);
});

test("disposed client cannot publish late results or start new marker calls", async () => {
  const waiting = deferred();
  let calls = 0;
  const old = createLibraryController(async () => { calls += 1; return waiting.promise; });
  const pending = old.start();
  old.dispose();
  const snapshot = old.getSnapshot();
  waiting.resolve(page([doc("old-account")]));
  await pending;
  await old.refreshMarkers(["old-account"]);
  assert.equal(old.getSnapshot(), snapshot);
  assert.equal(calls, 3);
  const current = createLibraryController(emptyApi);
  await current.start();
  assert.deepEqual(current.getSnapshot().recent.items, []);
});

test("batch markers replace removed membership and discard late visible-document batches", async () => {
  const late = deferred();
  const controller = createLibraryController(async (path, options) => {
    const id = JSON.parse(options.body).document_ids[0];
    return id === "old" ? late.promise : [];
  });
  const previous = controller.refreshMarkers(["old"]);
  await controller.refreshMarkers(["revoked"]);
  late.resolve([{ document_id: "old", is_favorite: true }]);
  await previous;
  assert.deepEqual(controller.getSnapshot().markers, { revoked: false });
});

test("favorite membership outside a loaded page is checked before removal", async () => {
  const methods = [];
  const controller = createLibraryController(async (path, options) => {
    if (path === "/api/v1/library/markers") return [{ document_id: "unloaded", is_favorite: true }];
    if (path.endsWith("/favorites/unloaded")) { methods.push(options.method); return { count: 1 }; }
    return page();
  });
  assert.equal(await controller.toggleFavorite({ documentId: "unloaded" }), true);
  assert.deepEqual(methods, ["DELETE"]);
});

test("count zero is a visible failed addition; refresh does not erase its error", async () => {
  const controller = createLibraryController(async (path) => {
    if (path === "/api/v1/library/markers") return [{ document_id: "a", is_favorite: false }];
    if (path.endsWith("/favorites/a")) return { count: 0 };
    return page();
  });
  assert.equal(await controller.toggleFavorite({ documentId: "a" }), false);
  assert.match(controller.getSnapshot().error, /No se pudo guardar/);
  assert.deepEqual(controller.getSnapshot().favorites.items, []);
});

test("conflict and revoked destination errors survive refresh", async () => {
  const controller = createLibraryController(async (path, options) => {
    if (options.method === "PATCH") throw Object.assign(new Error("Document or folder not found."), { status: 404 });
    if (path === "/api/v1/folders") throw Object.assign(new Error("Folder already exists."), { status: 409 });
    return emptyApi(path);
  });
  assert.equal(await controller.moveDocument({ documentId: "a" }, "missing"), false);
  assert.match(controller.getSnapshot().error, /not found/);
  assert.equal(await controller.addFolder("Duplicate"), null);
  assert.match(controller.getSnapshot().error, /already exists/);
});

test("404 while reading a selected folder closes it and clears its documents", async () => {
  const controller = createLibraryController(async () => { throw Object.assign(new Error("Folder not found."), { status: 404 }); });
  await controller.openFolder({ folderId: "revoked" });
  assert.equal(controller.getSnapshot().selectedFolder, null);
  assert.deepEqual(controller.getSnapshot().content.items, []);
  assert.match(controller.getSnapshot().error, /not found/);
});

test("a slow search cannot replace newer results or cross client disposal", async () => {
  const slow = deferred();
  const controller = createSearchController(async (path) => path.includes("q=old") ? slow.promise : { items: [doc("fresh")], total: 1 });
  const previous = controller.runSearch({ query: "old" });
  await controller.runSearch({ query: "new" });
  slow.resolve({ items: [doc("stale")], total: 1 });
  await previous;
  assert.equal(controller.getSnapshot().documents[0].documentId, "fresh");
  const pending = deferred();
  const oldClient = createSearchController(async () => pending.promise);
  const request = oldClient.start();
  oldClient.dispose();
  const snapshot = oldClient.getSnapshot();
  pending.resolve({ items: [doc("old-account")], total: 1 });
  await request;
  assert.equal(oldClient.getSnapshot(), snapshot);
});

test("restarting a controller after effect cleanup does not accept its first mount response", async () => {
  const initial = deferred();
  let calls = 0;
  const controller = createLibraryController(async (path) => {
    if (!path.includes("/recent?")) return emptyApi(path);
    calls += 1;
    return calls === 1 ? initial.promise : page([doc("current")]);
  });
  const old = controller.start();
  controller.dispose();
  await controller.start();
  initial.resolve(page([doc("previous-mount")]));
  await old;
  assert.equal(controller.getSnapshot().recent.items[0].documentId, "current");
});

test("an old favorite operation cannot unlock a new operation after cleanup", async () => {
  const old = deferred(), current = deferred();
  let reads = 0;
  const controller = createLibraryController(async (path) => {
    if (path === "/api/v1/library/markers") return ++reads === 1 ? old.promise : current.promise;
    if (path.endsWith("/favorites/a")) return { count: 1 };
    return page();
  });
  const first = controller.toggleFavorite({ documentId: "a" });
  controller.dispose();
  await controller.start();
  const second = controller.toggleFavorite({ documentId: "a" });
  old.resolve([{ document_id: "a", is_favorite: false }]);
  await first;
  assert.equal(await controller.toggleFavorite({ documentId: "a" }), false);
  assert.equal(reads, 2);
  current.resolve([{ document_id: "a", is_favorite: false }]);
  assert.equal(await second, true);
});
