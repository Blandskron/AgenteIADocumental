import { DEFAULT_CONVERSATION_TITLE } from "../../../entities/conversation/model/conversation.factory";

function normalizeConversation(conversation = {}, messages = [], selectedDocuments = []) {
  return {
    id: conversation.conversation_id,
    title: conversation.title || DEFAULT_CONVERSATION_TITLE,
    updatedAt: conversation.updated_at ? new Date(conversation.updated_at).getTime() : Date.now(),
    selectedDocuments,
    messages,
  };
}

function normalizeMessage(message = {}) {
  return {
    id: message.message_id,
    role: message.role || "assistant",
    content: message.content || "",
    sources: message.sources || [],
    metadata: message.metadata || {},
    createdAt: message.created_at || "",
  };
}

function normalizeSelectedDocument(documentId) {
  return {
    documentId,
    filename: "Documento seleccionado",
    status: "PROCESSED",
  };
}

export function listConversations(apiClient) {
  return apiClient("/api/v1/conversations", {
    method: "GET",
  }).then((payload) => (Array.isArray(payload) ? payload : []));
}

export async function hydrateConversation(apiClient, conversation) {
  const [messages, documentIdsPayload] = await Promise.all([
    apiClient(`/api/v1/conversations/${conversation.conversation_id}/messages`, { method: "GET" }),
    apiClient(`/api/v1/conversations/${conversation.conversation_id}/documents`, { method: "GET" }),
  ]);

  return normalizeConversation(
    conversation,
    Array.isArray(messages) ? messages.map(normalizeMessage) : [],
    Array.isArray(documentIdsPayload?.document_ids) ? documentIdsPayload.document_ids.map(normalizeSelectedDocument) : [],
  );
}

export async function listHydratedConversations(apiClient) {
  const conversations = await listConversations(apiClient);
  return Promise.all(conversations.map((conversation) => hydrateConversation(apiClient, conversation)));
}

export function createRemoteConversation(apiClient, title = DEFAULT_CONVERSATION_TITLE) {
  return apiClient("/api/v1/conversations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
}

export function updateRemoteConversation(apiClient, conversationId, payload) {
  return apiClient(`/api/v1/conversations/${conversationId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function deleteRemoteConversation(apiClient, conversationId) {
  return apiClient(`/api/v1/conversations/${conversationId}`, {
    method: "DELETE",
  });
}

export function addRemoteMessage(apiClient, conversationId, message) {
  return apiClient(`/api/v1/conversations/${conversationId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      role: message.role,
      content: message.content,
      sources: message.sources || [],
      metadata: message.metadata || {},
    }),
  }).then(normalizeMessage);
}

export function addRemoteConversationDocument(apiClient, conversationId, documentId) {
  return apiClient(`/api/v1/conversations/${conversationId}/documents/${documentId}`, {
    method: "POST",
  });
}

export function removeRemoteConversationDocument(apiClient, conversationId, documentId) {
  return apiClient(`/api/v1/conversations/${conversationId}/documents/${documentId}`, {
    method: "DELETE",
  });
}
