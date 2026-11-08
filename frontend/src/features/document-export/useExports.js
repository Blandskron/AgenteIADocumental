import { useLayoutEffect, useMemo, useSyncExternalStore } from "react";
import { createExportController } from "./export-controller.js";

export function useExports(client, scope) {
  const controller = useMemo(() => createExportController(client), [client, scope]);
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
  useLayoutEffect(() => { controller.start(); return () => controller.dispose(); }, [controller]);
  return { ...state, controller };
}
