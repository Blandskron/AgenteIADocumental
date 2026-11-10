export function buildConversationTitle(message: string, fallback: string) {
  return message.split("\n")[0].slice(0, 44) || fallback;
}
