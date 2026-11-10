import { createProfileController } from "@/features/profile/model/profile-controller.ts";
import type { MaybeClient } from "@/shared/api/types.ts";
import { useEffect, useMemo, useRef, useSyncExternalStore } from "react";
import type { Profile } from "../model/types.ts";

export function useProfile(
  client: MaybeClient,
  onUpdated?: (profile: Profile) => void,
) {
  const callback = useRef(onUpdated);
  callback.current = onUpdated;
  const controller = useMemo(
    () =>
      createProfileController(client, (profile) => callback.current?.(profile)),
    [client],
  );
  const state = useSyncExternalStore(
    controller.subscribe,
    controller.getSnapshot,
    controller.getSnapshot,
  );
  useEffect(() => {
    controller.start();
    return () => controller.dispose();
  }, [controller]);
  return {
    ...state,
    save: controller.save,
    reload: controller.reload,
    uploadAvatar: controller.uploadAvatar,
    removeAvatar: controller.removeAvatar,
    clearSuccess: controller.clearSuccess,
    acceptProfile: controller.acceptProfile,
  };
}
