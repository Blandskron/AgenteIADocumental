import { useEffect, useState } from "react";
import { loadPrivateAvatar } from "../api/private-avatar.js";

export function usePrivateAvatar(client, path) {
  const [state, setState] = useState(null);
  useEffect(() => {
    if (!client || !path) return;
    return loadPrivateAvatar(client, path, (result) => setState({ client, path, ...result }));
  }, [client, path]);
  const matches = state?.client === client && state?.path === path;
  return {
    src: matches ? state.src : null,
    error: matches ? state.error : null,
    onError: () => setState((current) => current?.client === client && current?.path === path
      ? { ...current, src: null, error: "No se pudo mostrar la foto." } : current),
  };
}
