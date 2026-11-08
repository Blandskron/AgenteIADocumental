import assert from "node:assert/strict";
import test from "node:test";
import { createChatMessagePdf, exportReferences } from "../src/features/document-export/api/document-export.api.js";

test("pending messages export a snapshot without a local message reference", async () => {
  for (const messageId of [undefined, "local-pending", "blandskron-local"]) {
    const result = await createChatMessagePdf(async (url, options) => {
      assert.equal(url, "/api/v1/exports/chat-message/pdf");
      const body = JSON.parse(options.body);
      assert.equal(body.conversation_id, "remote-conversation");
      assert.equal(body.message_id, null);
      assert.equal(body.answer, "Synthetic snapshot");
      return { export_id: "export", conversation_id: body.conversation_id, message_id: null };
    }, { conversationId: "remote-conversation", messageId, answer: "Synthetic snapshot" });
    assert.equal(result.exportId, "export");
    assert.equal(result.messageId, null);
  }
});

test("a local conversation exports without either foreign key", () => {
  for (const id of [null, undefined, "", "blandskron-local", "local-conversation"]) {
    assert.deepEqual(exportReferences(id, "remote-message"), { conversation_id: null, message_id: null });
  }
});

test("synchronized references are preserved and server failures propagate", async () => {
  assert.deepEqual(exportReferences("remote-conversation", "remote-message"), {
    conversation_id: "remote-conversation", message_id: "remote-message",
  });
  const error = new Error("Reference unavailable");
  await assert.rejects(createChatMessagePdf(async () => { throw error; }, {
    conversationId: "remote-conversation", messageId: "remote-message", answer: "Synthetic",
  }), (failure) => failure === error);
});

test("PDF source adapter preserves page and snippet without nonfinite numbers", async () => {
  await createChatMessagePdf(async (url, options) => {
    const source = JSON.parse(options.body).sources[0];
    assert.equal(source.page, 4);
    assert.equal(source.snippet, "Fragmento con ñ & texto");
    assert.equal(source.score, .75);
    return { export_id: "synthetic" };
  }, { answer: "synthetic", sources: [{ page_number: 4, snippet: "Fragmento con ñ & texto", score: .75 }] });
  for (const source of [{ score: Infinity }, { page: -1 }, { page: 1.5 }]) {
    let called = false;
    await assert.rejects(createChatMessagePdf(async () => { called = true; }, { answer: "synthetic", sources: [source] }));
    assert.equal(called, false);
  }
});
