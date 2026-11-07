export function getProfile(apiClient) {
  return apiClient("/api/v1/profile", {
    method: "GET",
    cache: "no-store",
  });
}

export function updateProfile(apiClient, payload, expectedVersion) {
  return apiClient("/api/v1/profile", {
    method: "PUT",
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

export function uploadProfilePicture(apiClient, file, expectedVersion) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("expected_version", String(expectedVersion));

  return apiClient("/api/v1/profile/upload", {
    method: "POST",
    body: formData,
  });
}

export function removeProfilePicture(apiClient, expectedVersion) {
  return apiClient("/api/v1/profile/avatar", { method: "DELETE", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ expected_version: expectedVersion }) });
}

export function getProfilePicture(apiClient, path, signal) {
  if (!/^\/api\/v1\/profile\/avatar\?version=[1-9][0-9]{0,18}$/.test(path || "")) {
    return Promise.reject(new Error("Referencia de foto no válida."));
  }
  return apiClient(path, { method: "GET", responseType: "blob", cache: "no-store", signal });
}

