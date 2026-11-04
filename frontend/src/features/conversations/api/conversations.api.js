import { DEFAULT_CONVERSATION_TITLE } from "../../../entities/conversation/model/conversation.factory";

const MESSAGE_PAGE_SIZE = 50;

function normalizeConversation(conversation, { messages, historyBefore }, selectedDocuments) {
  return {
    id: conversation.conversation_id,
    title: conversation.title || DEFAULT_CONVERSATION_TITLE,
    updatedAt: conversation.updated_at ? new Date(conversation.updated_at).getTime() : Date.now(),
    selectedDocuments,
    messages,
    historyBefore,
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
  const [history, documentIdsPayload] = await Promise.all([
    listMessagePage(apiClient, conversation.conversation_id),
    apiClient(`/api/v1/conversations/${conversation.conversation_id}/documents`, { method: "GET" }),
  ]);

  return normalizeConversation(
    conversation,
    history,
    Array.isArray(documentIdsPayload?.document_ids) ? documentIdsPayload.document_ids.map(normalizeSelectedDocument) : [],
  );
}

export async function listMessagePage(apiClient, conversationId, before) {
  const query = new URLSearchParams({ limit: String(MESSAGE_PAGE_SIZE) });
  if (before) query.set("before", before);
  const payload = await apiClient(`/api/v1/conversations/${conversationId}/messages?${query}`, { method: "GET" });
  const messages = Array.isArray(payload) ? payload.map(normalizeMessage) : [];
  return {
    messages,
    historyBefore: messages.length === MESSAGE_PAGE_SIZE ? messages[0].id : null,
  };
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
