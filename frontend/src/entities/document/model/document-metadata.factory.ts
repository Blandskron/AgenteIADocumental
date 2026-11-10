export function createDocumentMetadata(conversationId?: string | null) {
  return {
    source: "blandskron",
    conversation_id: conversationId,
  };
}
