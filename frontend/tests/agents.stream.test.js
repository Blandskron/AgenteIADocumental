import assert from "node:assert/strict";
import test from "node:test";

import {
  parseSseBuffer,
  streamAgentRunEvents,
} from "../src/features/agents/api/agents.stream.ts";

test("parseSseBuffer parses chunked step, approval and status events cleanly", () => {
  const chunk1 =
    'event: step\ndata: {"index":1,"tool":"search_documents","status":"ok"}\n\nevent: app';
  const r1 = parseSseBuffer(chunk1);
  assert.equal(r1.events.length, 1);
  assert.equal(r1.events[0].event, "step");
  assert.equal(r1.events[0].data.tool, "search_documents");

  const chunk2 =
    r1.remainder +
    'roval\ndata: {"approval_id":"apr_1","action":"save_studio_artifact"}\n\n';
  const r2 = parseSseBuffer(chunk2);
  assert.equal(r2.events.length, 1);
  assert.equal(r2.events[0].event, "approval");
  assert.equal(r2.events[0].data.approval_id, "apr_1");
  assert.equal(r2.remainder, "");
});

test("streamAgentRunEvents sends Bearer header and delivers streamed events", async () => {
  const received = [];
  let capturedHeaders = null;
  const encoder = new TextEncoder();

  const fakeFetch = async (_url, options) => {
    capturedHeaders = options.headers;
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(
          encoder.encode(
            'event: step\ndata: {"index":1,"tool":"get_document_chunks"}\n\n',
          ),
        );
        controller.enqueue(
          encoder.encode(
            'event: status\ndata: {"run_id":"run_9","status":"SUCCEEDED"}\n\n',
          ),
        );
        controller.close();
      },
    });
    return { ok: true, status: 200, body: stream };
  };

  await streamAgentRunEvents({
    baseUrl: "http://localhost:8019",
    runId: "run_9",
    accessToken: "synthetic.bearer.jwt",
    fetchImpl: fakeFetch,
    onEvent: (evt) => received.push(evt),
  });

  assert.equal(capturedHeaders.Authorization, "Bearer synthetic.bearer.jwt");
  assert.equal(received.length, 2);
  assert.equal(received[0].event, "step");
  assert.equal(received[1].event, "status");
  assert.equal(received[1].data.status, "SUCCEEDED");
});
