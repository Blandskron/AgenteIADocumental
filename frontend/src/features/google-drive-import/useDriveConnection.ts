import type { MaybeClient } from "@/shared/api/types.ts";
import { toError } from "@/shared/lib/errors.ts";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  disconnectGoogleDrive,
  getGoogleDriveConnection,
} from "./api/google-drive-import.api.ts";
import {
  clearDriveCallback,
  completeDriveAuthorization,
  startDriveAuthorization,
} from "./oauth-flow.ts";
import type { DriveConnection } from "./types.ts";

export function useDriveConnection(client: MaybeClient, scope: string | null) {
  const [state, setState] = useState<{
    connection: DriveConnection;
    error: string;
    busy: boolean;
  }>({ connection: { connected: false }, error: "", busy: false });
  const epoch = useRef(0);
  const invalidate = useCallback(() => {
    epoch.current++;
  }, []);
  useEffect(() => {
    const generation = ++epoch.current;
    setState({
      connection: { connected: false },
      error: "",
      busy: Boolean(client),
    });
    if (client) {
      const task =
        completeDriveAuthorization(client, scope) ||
        getGoogleDriveConnection(client);
      task
        .then((connection) => {
          clearDriveCallback(client, task);
          if (epoch.current === generation)
            setState({ connection, error: "", busy: false });
        })
        .catch((error) => {
          clearDriveCallback(client, task);
          if (epoch.current === generation)
            setState({
              connection: { connected: false },
              error: error.message,
              busy: false,
            });
        });
    }
    return invalidate;
  }, [client, scope, invalidate]);
  async function operate(
    operation: (isCurrent: () => boolean) => Promise<DriveConnection | void>,
  ) {
    const generation = ++epoch.current;
    setState((previous) => ({ ...previous, error: "", busy: true }));
    try {
      const connection = await operation(() => epoch.current === generation);
      if (epoch.current === generation && connection)
        setState({ connection, error: "", busy: false });
    } catch (caughtError) {
      const error = toError(caughtError);
      if (epoch.current === generation && error.status === 409) {
        try {
          const connection = await getGoogleDriveConnection(client);
          if (epoch.current === generation)
            setState({ connection, error: error.message, busy: false });
        } catch {
          if (epoch.current === generation)
            setState((previous) => ({
              ...previous,
              error: error.message,
              busy: false,
            }));
        }
      } else if (epoch.current === generation)
        setState((previous) => ({
          ...previous,
          error: error.message,
          busy: false,
        }));
    } finally {
      if (epoch.current === generation)
        setState((previous) => ({ ...previous, busy: false }));
    }
  }
  return {
    ...state,
    connect: () =>
      operate((isCurrent) =>
        startDriveAuthorization(client, scope, window, isCurrent),
      ),
    disconnect: () =>
      operate(() => {
        clearDriveCallback(client);
        return disconnectGoogleDrive(client, state.connection.version);
      }),
    refresh: () => operate(() => getGoogleDriveConnection(client)),
  };
}
