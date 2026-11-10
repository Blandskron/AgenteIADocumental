import type { MaybeClient } from "@/shared/api/types.ts";
import { requireClient } from "@/shared/api/types.ts";
import type { Profile, ProfileUpdate } from "../model/types.ts";

export function getProfile(apiClient: MaybeClient, signal?: AbortSignal) {
  return requireClient(apiClient)<Profile>("/api/v1/profile", {
    method: "GET",
    cache: "no-store",
    signal,
  });
}

export function updateProfile(
  apiClient: MaybeClient,
  payload: ProfileUpdate,
  expectedVersion: number,
  signal?: AbortSignal,
) {
  return requireClient(apiClient)<Profile>("/api/v1/profile", {
    method: "PUT",
    signal,
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      expected_version: expectedVersion,
      email: payload.email,
      phone_number: payload.phone_number,
      profile_picture_url: payload.profile_picture_url,
      additional_info: payload.additional_info,
    }),
  });
}

export function uploadProfilePicture(
  apiClient: MaybeClient,
  file: File,
  expectedVersion: number,
  signal?: AbortSignal,
) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("expected_version", String(expectedVersion));

  return requireClient(apiClient)<Profile>("/api/v1/profile/upload", {
    method: "POST",
    signal,
    body: formData,
  });
}

export function removeProfilePicture(
  apiClient: MaybeClient,
  expectedVersion: number,
  signal?: AbortSignal,
) {
  return requireClient(apiClient)<Profile>("/api/v1/profile/avatar", {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ expected_version: expectedVersion }),
    signal,
  });
}

export function getProfilePicture(
  apiClient: MaybeClient,
  path: string | null | undefined,
  signal?: AbortSignal,
) {
  if (
    !/^\/api\/v1\/profile\/avatar\?version=[1-9][0-9]{0,18}$/.test(path || "")
  ) {
    return Promise.reject(new Error("Referencia de foto no válida."));
  }
  return requireClient(apiClient)(path!, {
    method: "GET",
    responseType: "blob",
    cache: "no-store",
    signal,
  });
}
