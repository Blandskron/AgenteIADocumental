import type { MaybeClient } from "@/shared/api/types.ts";
import { useEffect, useMemo, useRef, useState } from "react";
import { createDriveController } from "./drive-controller.ts";
import type { DriveConnection } from "./types.ts";

export function useDriveImport(
  client: MaybeClient,
  scope: string | null,
  connection: DriveConnection,
  connectionBusy: boolean,
) {
  const [state, setState] = useState({ busy: false, error: "", success: "" });
  const key = JSON.stringify([
    scope,
    connection.version,
    connection.providerAccountId,
    connection.connected,
    connectionBusy,
  ]);
  const live = useRef<{ key: string; client: MaybeClient } | null>(null);
  // A new identity/version is visible to pending promises during render, before effect cleanup.
  if (live.current?.key !== key || live.current?.client !== client)
    live.current = { key, client };
  const controller = useMemo(
    () =>
      createDriveController({
        client,
        scope,
        context: () => (live.current?.key === key ? live.current : null),
        changed: (patch) => setState((value) => ({ ...value, ...patch })),
      }),
    [client, scope, key],
  );
  useEffect(() => {
    controller.start();
    setState({ busy: false, error: "", success: "" });
    return () => controller.stop();
  }, [controller]);
  return { ...state, controller };
}
