export function createUserMessage(content) {
  return { id: createLocalMessageId(), role: "user", content };
}

export function createAssistantMessage(content, sources = []) {
  return { id: createLocalMessageId(), role: "assistant", content, sources };
}

function createLocalMessageId() {
  return `local-${crypto.randomUUID ? crypto.randomUUID() : Date.now()}`;
}
