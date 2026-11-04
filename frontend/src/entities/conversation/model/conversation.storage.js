import { createConversation } from "./conversation.factory";
import { readJsonStorage, writeJsonStorage } from "../../../shared/lib/storage";

const CONVERSATIONS_STORAGE_KEY = "blandskron.conversations";

function scopedKey(scope) {
  return scope ? `${CONVERSATIONS_STORAGE_KEY}.${scope}` : CONVERSATIONS_STORAGE_KEY;
}

export function loadConversations(scope) {
  const stored = readJsonStorage(scopedKey(scope), []);
  return Array.isArray(stored) && stored.length ? stored : [createConversation()];
}

export function saveConversations(conversations, scope) {
  writeJsonStorage(scopedKey(scope), conversations);
}

export function updateStoredConversation(id, updater, scope) {
  const conversations = loadConversations(scope);
  const next = conversations.map((conversation) => {
    if (conversation.id !== id) return conversation;
    return { ...updater(conversation), updatedAt: Date.now() };
  });
  saveConversations(next, scope);
  return next;
}
