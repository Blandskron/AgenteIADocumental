export function buildConversationTitle(message, fallback) {
  return message.split("\n")[0].slice(0, 44) || fallback;
}
