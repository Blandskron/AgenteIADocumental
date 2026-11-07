import { useEffect, useMemo, useRef, useSyncExternalStore } from "react";
import { createProfileController } from "../model/profile-controller.js";

export function useProfile(client, onUpdated) {
  const callback = useRef(onUpdated);
  callback.current = onUpdated;
  const controller = useMemo(() => createProfileController(client, (profile) => callback.current?.(profile)), [client]);
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
  useEffect(() => {
    controller.start();
    return () => controller.dispose();
  }, [controller]);
  return { ...state, save: controller.save, reload: controller.reload, uploadAvatar: controller.uploadAvatar,
    removeAvatar: controller.removeAvatar, clearSuccess: controller.clearSuccess, acceptProfile: controller.acceptProfile };
}
