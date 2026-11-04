export function getProfile(apiClient) {
  return apiClient("/api/v1/profile", {
    method: "GET",
  });
}

export function updateProfile(apiClient, payload) {
  return apiClient("/api/v1/profile", {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      email: payload.email,
      phone_number: payload.phone_number,
      profile_picture_url: payload.profile_picture_url,
      additional_info: payload.additional_info,
    }),
  });
}

export function uploadProfilePicture(apiClient, file) {
  const formData = new FormData();
  formData.append("file", file);

  return apiClient("/api/v1/profile/upload", {
    method: "POST",
    body: formData,
  });
}

