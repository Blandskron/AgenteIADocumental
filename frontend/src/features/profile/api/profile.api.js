export function getProfile(apiClient, signal) {
  return apiClient("/api/v1/profile", {
    method: "GET",
    cache: "no-store",
    signal,
  });
}

export function updateProfile(apiClient, payload, expectedVersion, signal) {
  return apiClient("/api/v1/profile", {
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

export function uploadProfilePicture(apiClient, file, expectedVersion, signal) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("expected_version", String(expectedVersion));

  return apiClient("/api/v1/profile/upload", {
    method: "POST",
    signal,
    body: formData,
  });
}

export function removeProfilePicture(apiClient, expectedVersion, signal) {
  return apiClient("/api/v1/profile/avatar", { method: "DELETE", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ expected_version: expectedVersion }), signal });
}

export function getProfilePicture(apiClient, path, signal) {
  if (!/^\/api\/v1\/profile\/avatar\?version=[1-9][0-9]{0,18}$/.test(path || "")) {
    return Promise.reject(new Error("Referencia de foto no válida."));
  }
  return apiClient(path, { method: "GET", responseType: "blob", cache: "no-store", signal });
}

