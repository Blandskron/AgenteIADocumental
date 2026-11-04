import { useEffect, useMemo, useState } from "react";

import {
  createConversation,
  DEFAULT_CONVERSATION_TITLE,
} from "../../../entities/conversation/model/conversation.factory";
import { loadConversations, saveConversations } from "../../../entities/conversation/model/conversation.storage";
import { buildConversationTitle } from "../../../shared/utils/text";
import {
  addRemoteConversationDocument,
  addRemoteMessage,
  createRemoteConversation,
  deleteRemoteConversation,
  listHydratedConversations,
  removeRemoteConversationDocument,
  updateRemoteConversation,
} from "../api/conversations.api";

export function useConversations(scope, conversationClient = null) {
  const [conversations, setConversations] = useState(() => loadConversations(scope));
  const [activeId, setActiveId] = useState(() => conversations[0]?.id);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncError, setSyncError] = useState("");

  const activeConversation = useMemo(
    () => conversations.find((item) => item.id === activeId) || conversations[0],
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
        let remoteConversations = await listHydratedConversations(conversationClient);

        if (!remoteConversations.length) {
          const remote = await createRemoteConversation(conversationClient);
          remoteConversations = [
            {
              id: remote.conversation_id,
              title: remote.title || DEFAULT_CONVERSATION_TITLE,
              updatedAt: remote.updated_at ? new Date(remote.updated_at).getTime() : Date.now(),
              selectedDocuments: [],
              messages: [],
            },
          ];
        }

        if (!isMounted) return;
        setConversations(remoteConversations);
        setActiveId((current) => remoteConversations.find((conversation) => conversation.id === current)?.id || remoteConversations[0]?.id);
        saveConversations(remoteConversations, scope);
      } catch (requestError) {
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

  function updateConversation(id, updater) {
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

  function addMessage(message) {
    const conversationId = activeConversation.id;
    const optimisticMessage = message.id ? message : { ...message, id: `local-${crypto.randomUUID ? crypto.randomUUID() : Date.now()}` };
    const nextTitle =
      activeConversation.title === DEFAULT_CONVERSATION_TITLE && optimisticMessage.role === "user"
        ? buildConversationTitle(optimisticMessage.content, DEFAULT_CONVERSATION_TITLE)
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
              item.id === optimisticMessage.id ? { ...optimisticMessage, ...remoteMessage } : item,
            ),
          }));
        })
        .catch((requestError) => {
          setSyncError(requestError.message);
        });

      if (nextTitle !== activeConversation.title) {
        updateRemoteConversation(conversationClient, conversationId, { title: nextTitle }).catch((requestError) => {
          setSyncError(requestError.message);
        });
      }
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
          updatedAt: remote.updated_at ? new Date(remote.updated_at).getTime() : Date.now(),
          selectedDocuments: [],
          messages: [],
        };
      } catch (requestError) {
        setSyncError(requestError.message);
      }
    }

    setConversations((current) => [conversation, ...current]);
    setActiveId(conversation.id);
  }

  function setSelectedDocuments(documents) {
    const normalizedDocuments = uniqueDocuments(documents);
    const previousDocumentIds = new Set((activeConversation.selectedDocuments || []).map((document) => document.documentId));
    const nextDocumentIds = new Set(normalizedDocuments.map((document) => document.documentId));

    updateConversation(activeConversation.id, (conversation) => ({
      ...conversation,
      selectedDocuments: normalizedDocuments,
    }));

    if (conversationClient) {
      normalizedDocuments
        .filter((document) => !previousDocumentIds.has(document.documentId))
        .forEach((document) => {
          addRemoteConversationDocument(conversationClient, activeConversation.id, document.documentId).catch((requestError) => {
            setSyncError(requestError.message);
          });
        });

      [...previousDocumentIds]
        .filter((documentId) => !nextDocumentIds.has(documentId))
        .forEach((documentId) => {
          removeRemoteConversationDocument(conversationClient, activeConversation.id, documentId).catch((requestError) => {
            setSyncError(requestError.message);
          });
        });
    }
  }

  function deleteConversation(id) {
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
    setActiveId,
    addMessage,
    setSelectedDocuments,
    createNewConversation,
    deleteConversation,
  };
}

function uniqueDocuments(documents = []) {
  const seen = new Set();
  return documents.filter((document) => {
    if (!document?.documentId || seen.has(document.documentId)) return false;
    seen.add(document.documentId);
    return true;
  });
}
