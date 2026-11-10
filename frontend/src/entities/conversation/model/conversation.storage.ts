import { readJsonStorage, writeJsonStorage } from "@/shared/lib/storage.ts";
import { createConversation } from "./conversation.factory";
import type { Conversation } from "./types.ts";

const CONVERSATIONS_STORAGE_KEY = "blandskron.conversations";

function scopedKey(scope: string) {
  return scope
    ? `${CONVERSATIONS_STORAGE_KEY}.${scope}`
    : CONVERSATIONS_STORAGE_KEY;
}

export function loadConversations(scope: string) {
  const stored = readJsonStorage<Conversation[]>(scopedKey(scope), []);
  return Array.isArray(stored) && stored.length
    ? stored
    : [createConversation()];
}

export function saveConversations(
  conversations: Conversation[],
  scope: string,
) {
  writeJsonStorage(scopedKey(scope), conversations);
}

export function updateStoredConversation(
  id: string,
  updater: (conversation: Conversation) => Conversation,
  scope: string,
) {
  const conversations = loadConversations(scope);
  const next = conversations.map((conversation) => {
    if (conversation.id !== id) return conversation;
    return { ...updater(conversation), updatedAt: Date.now() };
  });
  saveConversations(next, scope);
  return next;
}
