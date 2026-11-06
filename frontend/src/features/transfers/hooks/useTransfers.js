import { useEffect, useMemo, useSyncExternalStore } from "react";
import { createTransferController } from "../transfer-controller.js";

export function useTransfers(apiClient, { autoLoad = true } = {}) {
  const controller = useMemo(() => createTransferController(apiClient), [apiClient]);
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot);
  useEffect(() => { controller.start(autoLoad); return () => controller.dispose(); }, [controller, autoLoad]);
  return { ...controller, ...state };
}
