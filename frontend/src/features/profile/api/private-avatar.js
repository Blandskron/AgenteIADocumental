import { getProfilePicture } from "../api/profile.api.js";

export function loadPrivateAvatar(client, path, publish, urls = URL) {
  let disposed = false;
  let objectUrl = null;
  const controller = new AbortController();
  Promise.resolve().then(() => {
    if (disposed) return null;
    return getProfilePicture(client, path, controller.signal);
  }).then((result) => {
    if (disposed || !result) return;
    if (result.contentType?.split(";")[0] !== "image/jpeg" || !result.blob || !result.blob.size || result.blob.size > 1048576) {
      throw new Error("Respuesta de foto no válida.");
    }
    objectUrl = urls.createObjectURL(result.blob);
    publish({ src: objectUrl, error: null });
  }).catch(() => {
    if (!disposed) publish({ src: null, error: "No se pudo cargar la foto." });
  });
  return () => {
    disposed = true;
    controller.abort();
    if (objectUrl) { urls.revokeObjectURL(objectUrl); objectUrl = null; }
  };
}
