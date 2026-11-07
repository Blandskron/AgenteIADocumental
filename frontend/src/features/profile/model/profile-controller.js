import { getProfile, removeProfilePicture, updateProfile, uploadProfilePicture } from "../api/profile.api.js";

const initial = () => ({ profile: null, formProfile: null, isLoading: true, isSaving: false,
  error: null, isConflict: false, saveSuccess: false });

export function createProfileController(client, onUpdated = () => {}) {
  let state = initial(), epoch = 0, running = false, pending = null;
  const listeners = new Set();
  const publish = (changes) => { state = { ...state, ...changes }; listeners.forEach((listener) => listener()); };
  const live = (generation) => running && generation === epoch;

  async function reload() {
    if (!running || !client || pending) return false;
    const generation = epoch, controller = new AbortController();
    pending = controller;
    publish({ isLoading: true, error: null });
    try {
      const data = await getProfile(client, controller.signal);
      if (!live(generation)) return false;
      // An earlier GET may complete after a confirmed mutation in another consumer.
      const profile = state.profile && state.profile.version > data.version ? state.profile : data;
      publish({ profile, formProfile: profile, isConflict: false, saveSuccess: false });
      return profile;
    } catch (error) {
      if (live(generation)) publish({ error: error.message || "No se pudo cargar el perfil." });
      return false;
    } finally {
      if (live(generation) && pending === controller) { pending = null; publish({ isLoading: false }); }
    }
  }

  async function write(operation, refreshForm) {
    if (!running || !client || !state.profile || pending) return false;
    const generation = epoch, controller = new AbortController(), version = state.profile.version;
    pending = controller;
    publish({ isSaving: true, error: null, saveSuccess: false });
    try {
      const profile = await operation(version, controller.signal);
      if (!live(generation)) return false;
      publish({ profile, ...(refreshForm ? { formProfile: profile } : {}), isConflict: false, saveSuccess: refreshForm });
      onUpdated(profile);
      return profile;
    } catch (error) {
      if (live(generation)) publish({ isConflict: error.status === 409, error: error.status === 409
        ? "El perfil cambió en otra sesión. Tus cambios siguen en el formulario; recarga el perfil antes de volver a guardar."
        : error.message || "No se pudo guardar el perfil." });
      return false;
    } finally {
      if (live(generation) && pending === controller) { pending = null; publish({ isSaving: false }); }
    }
  }

  return {
    getSnapshot: () => state,
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); },
    start() { running = true; epoch++; publish(initial()); return reload(); },
    dispose() { running = false; epoch++; pending?.abort(); pending = null; },
    reload,
    save: (payload) => write((version, signal) => updateProfile(client, payload, version, signal), true),
    uploadAvatar: (file) => write((version, signal) => uploadProfilePicture(client, file, version, signal), false),
    removeAvatar: () => write((version, signal) => removeProfilePicture(client, version, signal), false),
    clearSuccess: () => publish({ saveSuccess: false }),
    acceptProfile(profile) {
      if (running && (!state.profile || profile.version >= state.profile.version)) publish({ profile });
    },
  };
}
