import type { Message } from "@/entities/conversation/model/types.ts";
import { useEffect, useRef } from "react";

export function useScrollToBottom({
  conversationId,
  message,
  busy,
  enabled,
}: {
  conversationId: string;
  message?: Message;
  busy: boolean;
  enabled: boolean;
}) {
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!enabled) return;
    ref.current?.scrollTo({
      top: ref.current.scrollHeight,
      behavior: "smooth",
    });
  }, [conversationId, message, busy, enabled]);

  return ref;
}
