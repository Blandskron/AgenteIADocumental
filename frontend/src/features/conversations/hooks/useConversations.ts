import type {
  Conversation,
  Message,
} from "@/entities/conversation/model/types.ts";
import type { DocumentItem } from "@/entities/document/model/types.ts";
import type { MaybeClient } from "@/shared/api/types.ts";
import { toError } from "@/shared/lib/errors.ts";
import { useEffect, useMemo, useState } from "react";

import {
  createConversation,
  DEFAULT_CONVERSATION_TITLE,
} from "@/entities/conversation/model/conversation.factory";
import {
  loadConversations,
  saveConversations,
} from "@/entities/conversation/model/conversation.storage";
import {
  addRemoteConversationDocument,
  addRemoteMessage,
  createRemoteConversation,
  deleteRemoteConversation,
  listHydratedConversations,
  listMessagePage,
  removeRemoteConversationDocument,
  updateRemoteConversation,
} from "@/features/conversations/api/conversations.api";
import { buildConversationTitle } from "@/shared/utils/text.ts";

export function useConversations(
  scope: string,
  conversationClient: MaybeClient = null,
) {
  const [conversations, setConversations] = useState(() =>
    loadConversations(scope),
  );
  const [activeId, setActiveId] = useState(() => conversations[0]?.id);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncError, setSyncError] = useState("");
  const [historyRequest, setHistoryRequest] = useState<{
    id: string;
    pending: boolean;
    error?: string;
  } | null>(null);

  const activeConversation = useMemo(
    () =>
      conversations.find((item) => item.id === activeId) || conversations[0],
    [activeId, conversations],
  );

  useEffect(() => {
    saveConversations(conversations, scope);
  }, [conversations, scope]);

  useEffect(() => {
    const nextConversations = loadConversations(scope);
    setConversations(nextConversations);
    setActiveId(nextConversations[0]?.id);
  }, [scope]);

  useEffect(() => {
    if (!conversationClient) return;

    let isMounted = true;

    async function loadRemoteConversations() {
      setIsSyncing(true);
      setSyncError("");

      try {
        let remoteConversations =
          await listHydratedConversations(conversationClient);

        if (!remoteConversations.length) {
          const remote = await createRemoteConversation(conversationClient);
          remoteConversations = [
            {
              id: remote.conversation_id,
              title: remote.title || DEFAULT_CONVERSATION_TITLE,
              updatedAt: remote.updated_at
                ? new Date(remote.updated_at).getTime()
                : Date.now(),
              selectedDocuments: [],
              messages: [],
            },
          ];
        }

        if (!isMounted) return;
        setConversations(remoteConversations);
        setActiveId(
          (current) =>
            remoteConversations.find(
              (conversation) => conversation.id === current,
            )?.id || remoteConversations[0]?.id,
        );
        saveConversations(remoteConversations, scope);
      } catch (caughtError) {
        const requestError = toError(caughtError);
        if (isMounted) setSyncError(requestError.message);
      } finally {
        if (isMounted) setIsSyncing(false);
      }
    }

    loadRemoteConversations();

    return () => {
      isMounted = false;
    };
  }, [conversationClient, scope]);

  function updateConversation(
    id: string,
    updater: (conversation: Conversation) => Conversation,
  ) {
    setConversations((current) => {
      const next = current.map((conversation) => {
        if (conversation.id !== id) return conversation;
        const updated = updater(conversation);
        return { ...updated, updatedAt: Date.now() };
      });
      saveConversations(next, scope);
      return next;
    });
  }

  function addMessage(message: Message) {
    const conversationId = activeConversation.id;
    const optimisticMessage = message.id
      ? message
      : {
          ...message,
          id: `local-${crypto.randomUUID ? crypto.randomUUID() : Date.now()}`,
        };
    const nextTitle =
      activeConversation.title === DEFAULT_CONVERSATION_TITLE &&
      optimisticMessage.role === "user"
        ? buildConversationTitle(
            optimisticMessage.content,
            DEFAULT_CONVERSATION_TITLE,
          )
        : activeConversation.title;

    updateConversation(activeConversation.id, (conversation) => ({
      ...conversation,
      title: nextTitle,
      messages: [...conversation.messages, optimisticMessage],
    }));

    if (conversationClient) {
      addRemoteMessage(conversationClient, conversationId, optimisticMessage)
        .then((remoteMessage) => {
          updateConversation(conversationId, (conversation) => ({
            ...conversation,
            messages: conversation.messages.map((item) =>
              item.id === optimisticMessage.id
                ? { ...optimisticMessage, ...remoteMessage }
                : item,
            ),
          }));
        })
        .catch((requestError) => {
          setSyncError(requestError.message);
        });

      if (nextTitle !== activeConversation.title) {
        updateRemoteConversation(conversationClient, conversationId, {
          title: nextTitle,
        }).catch((requestError) => {
          setSyncError(requestError.message);
        });
      }
    }
  }

  async function loadOlderMessages() {
    const { id, historyBefore } = activeConversation || {};
    if (!conversationClient || !historyBefore || historyRequest?.pending)
      return;

    setHistoryRequest({ id, pending: true });
    try {
      const page = await listMessagePage(conversationClient, id, historyBefore);
      setConversations((current) =>
        current.map((conversation) => {
          if (
            conversation.id !== id ||
            conversation.historyBefore !== historyBefore
          )
            return conversation;
          const loadedIds = new Set(
            conversation.messages.map((message) => message.id),
          );
          return {
            ...conversation,
            historyBefore: page.historyBefore,
            messages: [
              ...page.messages.filter((message) => !loadedIds.has(message.id)),
              ...conversation.messages,
            ],
          };
        }),
      );
      setHistoryRequest(null);
    } catch (caughtError) {
      const requestError = toError(caughtError);
      setHistoryRequest({ id, pending: false, error: requestError.message });
    }
  }

  async function createNewConversation() {
    let conversation = createConversation();

    if (conversationClient) {
      try {
        const remote = await createRemoteConversation(conversationClient);
        conversation = {
          id: remote.conversation_id,
          title: remote.title || DEFAULT_CONVERSATION_TITLE,
          updatedAt: remote.updated_at
            ? new Date(remote.updated_at).getTime()
            : Date.now(),
          selectedDocuments: [],
          messages: [],
        };
      } catch (caughtError) {
        const requestError = toError(caughtError);
        setSyncError(requestError.message);
      }
    }

    setConversations((current) => [conversation, ...current]);
    setActiveId(conversation.id);
  }

  function setSelectedDocuments(documents: DocumentItem[]) {
    const normalizedDocuments = uniqueDocuments(documents);
    const previousDocumentIds = new Set(
      (activeConversation.selectedDocuments || []).map(
        (document) => document.documentId,
      ),
    );
    const nextDocumentIds = new Set(
      normalizedDocuments.map((document) => document.documentId),
    );

    updateConversation(activeConversation.id, (conversation) => ({
      ...conversation,
      selectedDocuments: normalizedDocuments,
    }));

    if (conversationClient) {
      normalizedDocuments
        .filter((document) => !previousDocumentIds.has(document.documentId))
        .forEach((document) => {
          addRemoteConversationDocument(
            conversationClient,
            activeConversation.id,
            document.documentId,
          ).catch((requestError) => {
            setSyncError(requestError.message);
          });
        });

      [...previousDocumentIds]
        .filter((documentId) => !nextDocumentIds.has(documentId))
        .forEach((documentId) => {
          removeRemoteConversationDocument(
            conversationClient,
            activeConversation.id,
            documentId,
          ).catch((requestError) => {
            setSyncError(requestError.message);
          });
        });
    }
  }

  function deleteConversation(id: string) {
    setConversations((current) => {
      const next = current.filter((conversation) => conversation.id !== id);

      if (!next.length) {
        const fresh = createConversation();
        setActiveId(fresh.id);
        return [fresh];
      }

      if (id === activeId) {
        setActiveId(next[0].id);
      }

      return next;
    });

    if (conversationClient) {
      deleteRemoteConversation(conversationClient, id).catch((requestError) => {
        setSyncError(requestError.message);
      });
    }
  }

  return {
    conversations,
    activeConversation,
    activeId,
    isSyncing,
    syncError,
    historyLoading: Boolean(historyRequest?.pending),
    historyError:
      historyRequest?.id === activeConversation?.id
        ? historyRequest?.error
        : "",
    loadOlderMessages,
    setActiveId,
    addMessage,
    setSelectedDocuments,
    createNewConversation,
    deleteConversation,
  };
}

function uniqueDocuments(documents: DocumentItem[] = []) {
  const seen = new Set();
  return documents.filter((document) => {
    if (!document?.documentId || seen.has(document.documentId)) return false;
    seen.add(document.documentId);
    return true;
  });
}
