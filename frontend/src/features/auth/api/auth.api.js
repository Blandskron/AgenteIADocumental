import { env } from "../../../app/config/env";
import { httpRequest } from "../../../shared/api/httpClient";

export function loginRequest(credentials) {
  return httpRequest(env.authBaseUrl, "/api/users/login/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(credentials),
  });
}

export function refreshTokenRequest(refresh) {
  return httpRequest(env.authBaseUrl, "/api/users/token/refresh/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  });
}

export function meRequest(accessToken) {
  return httpRequest(env.authBaseUrl, "/api/users/me/", {
    method: "GET",
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}
