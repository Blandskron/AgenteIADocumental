import type { AgentStreamEvent } from "../types.ts";

/**
 * Parses buffered SSE blocks (`event: ...\ndata: ...\n\n`) into typed AgentStreamEvent objects.
 */
export function parseSseBuffer(buffer: string): {
  events: AgentStreamEvent[];
  remainder: string;
} {
  const normalized = buffer.replace(/\r\n/g, "\n");
  const parts = normalized.split("\n\n");
  const remainder = parts.pop() ?? "";
  const events: AgentStreamEvent[] = [];

  for (const block of parts) {
    const trimmed = block.trim();
    if (!trimmed) continue;
    let eventName: AgentStreamEvent["event"] = "message";
    const dataLines: string[] = [];

    for (const line of trimmed.split("\n")) {
      if (line.startsWith("event:")) {
        const rawEvent = line.slice("event:".length).trim();
        if (
          rawEvent === "step" ||
          rawEvent === "approval" ||
          rawEvent === "status"
        ) {
          eventName = rawEvent;
        }
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice("data:".length).trim());
      }
    }

    if (dataLines.length === 0) continue;
    const rawData = dataLines.join("\n");
    let parsed: unknown = rawData;
    try {
      parsed = JSON.parse(rawData);
    } catch {
      // Keep plain text payload if not JSON.
    }
    events.push({ event: eventName, data: parsed });
  }

  return { events, remainder };
}

export interface StreamAgentRunOptions {
  baseUrl: string;
  runId: string;
  accessToken: string;
  signal?: AbortSignal;
  fetchImpl?: typeof fetch;
  onEvent: (event: AgentStreamEvent) => void;
}

/**
 * Streams SSE events from GET /api/v1/agents/runs/{runId}/stream using Authorization: Bearer.
 */
export async function streamAgentRunEvents({
  baseUrl,
  runId,
  accessToken,
  signal,
  fetchImpl = fetch,
  onEvent,
}: StreamAgentRunOptions): Promise<void> {
  const url = `${baseUrl.replace(/\/+$/, "")}/api/v1/agents/runs/${encodeURIComponent(runId)}/stream`;
  const response = await fetchImpl(url, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      Accept: "text/event-stream",
    },
    signal,
  });

  if (!response.ok) {
    throw new Error(`SSE stream failed with HTTP ${response.status}`);
  }
  if (!response.body) {
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const { events, remainder } = parseSseBuffer(buffer);
      buffer = remainder;
      for (const evt of events) {
        onEvent(evt);
      }
    }
    if (buffer.trim()) {
      const { events } = parseSseBuffer(`${buffer}\n\n`);
      for (const evt of events) {
        onEvent(evt);
      }
    }
  } finally {
    reader.releaseLock();
  }
}
