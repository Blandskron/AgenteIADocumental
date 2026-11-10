import {
  getProfile,
  removeProfilePicture,
  updateProfile,
  uploadProfilePicture,
} from "@/features/profile/api/profile.api.ts";
import type { MaybeClient } from "@/shared/api/types.ts";
import { toError } from "@/shared/lib/errors.ts";
import type { Profile, ProfileUpdate } from "./types.ts";

interface State {
  profile: Profile | null;
  formProfile: Profile | null;
  isLoading: boolean;
  isSaving: boolean;
  error: string | null;
  isConflict: boolean;
  saveSuccess: boolean;
}
const initial = (): State => ({
  profile: null,
  formProfile: null,
  isLoading: true,
  isSaving: false,
  error: null,
  isConflict: false,
  saveSuccess: false,
});

export function createProfileController(
  client: MaybeClient,
  onUpdated: (profile: Profile) => void = () => {},
) {
  let state = initial(),
    epoch = 0,
    running = false,
    pending: AbortController | null = null;
  const listeners = new Set<() => void>();
  const publish = (changes: Partial<State>) => {
    state = { ...state, ...changes };
    listeners.forEach((listener) => listener());
  };
  const live = (generation: number) => running && generation === epoch;

  async function reload() {
    if (!running || !client || pending) return false;
    const generation = epoch,
      controller = new AbortController();
    pending = controller;
    publish({ isLoading: true, error: null });
    try {
      const data = await getProfile(client, controller.signal);
      if (!live(generation)) return false;
      // An earlier GET may complete after a confirmed mutation in another consumer.
      const profile =
        state.profile && state.profile.version > data.version
          ? state.profile
          : data;
      publish({
        profile,
        formProfile: profile,
        isConflict: false,
        saveSuccess: false,
      });
      return profile;
    } catch (caughtError) {
      const error = toError(caughtError);
      if (live(generation))
        publish({ error: error.message || "No se pudo cargar el perfil." });
      return false;
    } finally {
      if (live(generation) && pending === controller) {
        pending = null;
        publish({ isLoading: false });
      }
    }
  }

  async function write(
    operation: (version: number, signal: AbortSignal) => Promise<Profile>,
    refreshForm: boolean,
  ) {
    if (!running || !client || !state.profile || pending) return false;
    const generation = epoch,
      controller = new AbortController(),
      version = state.profile.version;
    pending = controller;
    publish({ isSaving: true, error: null, saveSuccess: false });
    try {
      const profile = await operation(version, controller.signal);
      if (!live(generation)) return false;
      publish({
        profile,
        ...(refreshForm ? { formProfile: profile } : {}),
        isConflict: false,
        saveSuccess: refreshForm,
      });
      onUpdated(profile);
      return profile;
    } catch (caughtError) {
      const error = toError(caughtError);
      if (live(generation))
        publish({
          isConflict: error.status === 409,
          error:
            error.status === 409
              ? "El perfil cambió en otra sesión. Tus cambios siguen en el formulario; recarga el perfil antes de volver a guardar."
              : error.message || "No se pudo guardar el perfil.",
        });
      return false;
    } finally {
      if (live(generation) && pending === controller) {
        pending = null;
        publish({ isSaving: false });
      }
    }
  }

  return {
    getSnapshot: () => state,
    subscribe(listener: () => void) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    start() {
      running = true;
      epoch++;
      publish(initial());
      return reload();
    },
    dispose() {
      running = false;
      epoch++;
      pending?.abort();
      pending = null;
    },
    reload,
    save: (payload: ProfileUpdate) =>
      write(
        (version, signal) => updateProfile(client, payload, version, signal),
        true,
      ),
    uploadAvatar: (file: File) =>
      write(
        (version, signal) =>
          uploadProfilePicture(client, file, version, signal),
        false,
      ),
    removeAvatar: () =>
      write(
        (version, signal) => removeProfilePicture(client, version, signal),
        false,
      ),
    clearSuccess: () => publish({ saveSuccess: false }),
    acceptProfile(profile: Profile) {
      if (
        running &&
        (!state.profile || profile.version >= state.profile.version)
      )
        publish({ profile });
    },
  };
}
