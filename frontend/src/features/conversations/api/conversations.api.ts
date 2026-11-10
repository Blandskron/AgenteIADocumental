import { DEFAULT_CONVERSATION_TITLE } from "@/entities/conversation/model/conversation.factory";
import type {
  Conversation,
  Message,
  Source,
} from "@/entities/conversation/model/types.ts";
import type { DocumentItem } from "@/entities/document/model/types.ts";
import type { MaybeClient } from "@/shared/api/types.ts";
import { requireClient } from "@/shared/api/types.ts";
interface ConversationDto {
  conversation_id: string;
  title?: string;
  updated_at?: string;
}
interface MessageDto {
  message_id?: string;
  role?: string;
  content?: string;
  sources?: Source[];
  metadata?: Record<string, unknown>;
  created_at?: string;
}

const MESSAGE_PAGE_SIZE = 50;

function normalizeConversation(
  conversation: ConversationDto,
  {
    messages,
    historyBefore,
  }: { messages: Message[]; historyBefore: string | null },
  selectedDocuments: DocumentItem[],
): Conversation {
  return {
    id: conversation.conversation_id || "",
    title: conversation.title || DEFAULT_CONVERSATION_TITLE,
    updatedAt: conversation.updated_at
      ? new Date(conversation.updated_at).getTime()
      : Date.now(),
    selectedDocuments,
    messages,
    historyBefore,
  };
}

function normalizeMessage(message: MessageDto = {}) {
  return {
    id: message.message_id || "",
    role: message.role || "assistant",
    content: message.content || "",
    sources: message.sources || [],
    metadata: message.metadata || {},
    createdAt: message.created_at || "",
  };
}

function normalizeSelectedDocument(documentId: string) {
  return {
    documentId,
    filename: "Documento seleccionado",
    status: "PROCESSED",
  };
}

export function listConversations(apiClient: MaybeClient) {
  return requireClient(apiClient)<ConversationDto[]>("/api/v1/conversations", {
    method: "GET",
  }).then((payload) => (Array.isArray(payload) ? payload : []));
}

export async function hydrateConversation(
  apiClient: MaybeClient,
  conversation: ConversationDto,
) {
  const [history, documentIdsPayload] = await Promise.all([
    listMessagePage(apiClient, conversation.conversation_id),
    requireClient(apiClient)<{ document_ids: string[] }>(
      `/api/v1/conversations/${conversation.conversation_id}/documents`,
      { method: "GET" },
    ),
  ]);

  return normalizeConversation(
    conversation,
    history,
    Array.isArray(documentIdsPayload?.document_ids)
      ? documentIdsPayload.document_ids.map(normalizeSelectedDocument)
      : [],
  );
}

export async function listMessagePage(
  apiClient: MaybeClient,
  conversationId: string,
  before?: string | null,
) {
  const query = new URLSearchParams({ limit: String(MESSAGE_PAGE_SIZE) });
  if (before) query.set("before", before);
  const payload = await requireClient(apiClient)<MessageDto[]>(
    `/api/v1/conversations/${conversationId}/messages?${query}`,
    { method: "GET" },
  );
  const messages = Array.isArray(payload) ? payload.map(normalizeMessage) : [];
  return {
    messages,
    historyBefore:
      messages.length === MESSAGE_PAGE_SIZE ? messages[0].id : null,
  };
}

export async function listHydratedConversations(apiClient: MaybeClient) {
  const conversations = await listConversations(apiClient);
  return Promise.all(
    conversations.map((conversation) =>
      hydrateConversation(apiClient, conversation),
    ),
  );
}

export function createRemoteConversation(
  apiClient: MaybeClient,
  title = DEFAULT_CONVERSATION_TITLE,
) {
  return requireClient(apiClient)<ConversationDto>("/api/v1/conversations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
}

export function updateRemoteConversation(
  apiClient: MaybeClient,
  conversationId: string,
  payload: { title: string },
) {
  return requireClient(apiClient)(`/api/v1/conversations/${conversationId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function deleteRemoteConversation(
  apiClient: MaybeClient,
  conversationId: string,
) {
  return requireClient(apiClient)(`/api/v1/conversations/${conversationId}`, {
    method: "DELETE",
  });
}

export function addRemoteMessage(
  apiClient: MaybeClient,
  conversationId: string,
  message: Message & { metadata?: Record<string, unknown> },
) {
  return requireClient(apiClient)<Parameters<typeof normalizeMessage>[0]>(
    `/api/v1/conversations/${conversationId}/messages`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        role: message.role,
        content: message.content,
        sources: message.sources || [],
        metadata: message.metadata || {},
      }),
    },
  ).then(normalizeMessage);
}

export function addRemoteConversationDocument(
  apiClient: MaybeClient,
  conversationId: string,
  documentId: string,
) {
  return requireClient(apiClient)(
    `/api/v1/conversations/${conversationId}/documents/${documentId}`,
    {
      method: "POST",
    },
  );
}

export function removeRemoteConversationDocument(
  apiClient: MaybeClient,
  conversationId: string,
  documentId: string,
) {
  return requireClient(apiClient)(
    `/api/v1/conversations/${conversationId}/documents/${documentId}`,
    {
      method: "DELETE",
    },
  );
}
