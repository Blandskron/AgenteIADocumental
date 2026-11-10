import type { MaybeClient } from "@/shared/api/types.ts";
import { useLayoutEffect, useMemo, useSyncExternalStore } from "react";
import { createExportController } from "./export-controller.ts";

export function useExports(client: MaybeClient, scope: string) {
  const controller = useMemo(
    () => createExportController(scope ? client : null),
    [client, scope],
  );
  const state = useSyncExternalStore(
    controller.subscribe,
    controller.getSnapshot,
    controller.getSnapshot,
  );
  useLayoutEffect(() => {
    controller.start();
    return () => controller.dispose();
  }, [controller]);
  return { ...state, controller };
}
