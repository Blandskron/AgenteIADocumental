import type { Message, Source } from "@/entities/conversation/model/types.ts";
export function createUserMessage(content: string): Message {
  return { id: createLocalMessageId(), role: "user", content };
}

export function createAssistantMessage(
  content: string,
  sources: Source[] = [],
): Message {
  return { id: createLocalMessageId(), role: "assistant", content, sources };
}

function createLocalMessageId() {
  return `local-${crypto.randomUUID ? crypto.randomUUID() : Date.now()}`;
}
