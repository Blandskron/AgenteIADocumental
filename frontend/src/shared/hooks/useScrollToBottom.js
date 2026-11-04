import { useEffect, useRef } from "react";

export function useScrollToBottom(dependencies, { enabled = true } = {}) {
  const ref = useRef(null);

  useEffect(() => {
    if (!enabled) return;
    ref.current?.scrollTo({ top: ref.current.scrollHeight, behavior: "smooth" });
  }, [...dependencies, enabled]);

  return ref;
}
