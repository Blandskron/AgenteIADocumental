import { loadPrivateAvatar } from "@/features/profile/api/private-avatar.ts";
import type { MaybeClient } from "@/shared/api/types.ts";
import { useEffect, useState } from "react";
import type { AvatarState } from "../api/private-avatar.ts";

export function usePrivateAvatar(client: MaybeClient, path?: string | null) {
  const [state, setState] = useState<
    (AvatarState & { client: MaybeClient; path: string }) | null
  >(null);
  useEffect(() => {
    if (!client || !path) return;
    return loadPrivateAvatar(client, path, (result) =>
      setState({ client, path, ...result }),
    );
  }, [client, path]);
  const matches = state?.client === client && state?.path === path;
  return {
    src: matches ? state!.src : null,
    error: matches ? state!.error : null,
    onError: () =>
      setState((current) =>
        current?.client === client && current?.path === path
          ? { ...current, src: null, error: "No se pudo mostrar la foto." }
          : current,
      ),
  };
}
