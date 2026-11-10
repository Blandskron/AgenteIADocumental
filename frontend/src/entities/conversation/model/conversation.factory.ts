import type { Conversation } from "./types.ts";
export const DEFAULT_CONVERSATION_TITLE = "Nuevo chat";

export function createSessionId() {
  return `blandskron-${crypto.randomUUID ? crypto.randomUUID() : Date.now()}`;
}

export function createConversation(
  title = DEFAULT_CONVERSATION_TITLE,
): Conversation {
  return {
    id: createSessionId(),
    title,
    updatedAt: Date.now(),
    selectedDocuments: [],
    messages: [
      {
        role: "assistant",
        content:
          "Soy Blandskron Documental. Puedo consultar documentos existentes o analizar un archivo que adjuntes en este chat.",
      },
    ],
  };
}
