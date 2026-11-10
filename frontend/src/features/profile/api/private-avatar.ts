import { getProfilePicture } from "@/features/profile/api/profile.api.ts";
import type { MaybeClient } from "@/shared/api/types.ts";
export interface AvatarState {
  src: string | null;
  error: string | null;
}

export function loadPrivateAvatar(
  client: MaybeClient,
  path: string,
  publish: (value: AvatarState) => void,
  urls = URL,
) {
  let disposed = false;
  let objectUrl: string | null = null;
  const controller = new AbortController();
  Promise.resolve()
    .then(() => {
      if (disposed) return null;
      return getProfilePicture(client, path, controller.signal);
    })
    .then((result) => {
      if (disposed || !result) return;
      if (
        result.contentType?.split(";")[0] !== "image/jpeg" ||
        !result.blob ||
        !result.blob.size ||
        result.blob.size > 1048576
      ) {
        throw new Error("Respuesta de foto no válida.");
      }
      objectUrl = urls.createObjectURL(result.blob);
      publish({ src: objectUrl, error: null });
    })
    .catch(() => {
      if (!disposed)
        publish({ src: null, error: "No se pudo cargar la foto." });
    });
  return () => {
    disposed = true;
    controller.abort();
    if (objectUrl) {
      urls.revokeObjectURL(objectUrl);
      objectUrl = null;
    }
  };
}
