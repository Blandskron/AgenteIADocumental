import { useEffect, useMemo, useRef, useState } from "react";
import { createDriveController } from "./drive-controller.js";

export function useDriveImport(client, scope, connection, connectionBusy) {
  const [state, setState] = useState({ busy: false, error: "", success: "" });
  const key = JSON.stringify([scope, connection.version, connection.providerAccountId, connection.connected, connectionBusy]);
  const live = useRef();
  // A new identity/version is visible to pending promises during render, before effect cleanup.
  if (live.current?.key !== key || live.current?.client !== client) live.current = { key, client };
  const controller = useMemo(() => createDriveController({ client, scope, context: () => live.current,
    changed: (patch) => setState((value) => ({ ...value, ...patch })) }), [client, scope, key]);
  useEffect(() => { controller.start(); setState({ busy: false, error: "", success: "" }); return () => controller.stop(); }, [controller]);
  return { ...state, controller };
}
