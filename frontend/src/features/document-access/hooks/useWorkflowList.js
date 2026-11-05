import { useCallback, useEffect, useRef, useState } from "react";

export function useWorkflowList(client, loader) {
  const [items, setItems] = useState([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const nextOffset = useRef(0);
  const request = useRef(0);
  const busy = useRef(false);

  const load = useCallback(async (reset) => {
    if (!reset && busy.current) return;
    const version = ++request.current;
    busy.current = true;
    setLoading(true);
    setError("");
    try {
      const page = await loader(client, reset ? 0 : nextOffset.current);
      if (version !== request.current) return;
      nextOffset.current = page.nextOffset;
      setItems((previous) => {
        const rows = reset ? page.items : [...previous, ...page.items];
        return [...new Map(rows.map((row) => [row.notificationId || row.assignmentId, row])).values()];
      });
      setHasMore(page.hasMore);
    } catch (failure) {
      if (version === request.current) setError(failure.message);
    } finally {
      if (version === request.current) {
        busy.current = false;
        setLoading(false);
      }
    }
  }, [client, loader]);

  useEffect(() => {
    setItems([]);
    setHasMore(false);
    nextOffset.current = 0;
    load(true);
    return () => { request.current += 1; busy.current = false; };
  }, [load]);

  return { items, hasMore, loading, error, reload: () => load(true), loadMore: () => load(false) };
}
