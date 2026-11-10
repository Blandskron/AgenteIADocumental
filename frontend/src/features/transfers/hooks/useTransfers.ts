import { createTransferController } from "@/features/transfers/transfer-controller.ts";
import type { MaybeClient } from "@/shared/api/types.ts";
import { useEffect, useMemo, useSyncExternalStore } from "react";

export function useTransfers(apiClient: MaybeClient, { autoLoad = true } = {}) {
  const controller = useMemo(
    () => createTransferController(apiClient),
    [apiClient],
  );
  const state = useSyncExternalStore(
    controller.subscribe,
    controller.getSnapshot,
  );
  useEffect(() => {
    controller.start(autoLoad);
    return () => controller.dispose();
  }, [controller, autoLoad]);
  return { ...controller, ...state };
}
