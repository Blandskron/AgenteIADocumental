import { env } from "@/app/config/env.ts";
import type {
  AuthUserPayload,
  Credentials,
  TokenPayload,
} from "@/entities/auth/model/types.ts";
import { httpRequest } from "@/shared/api/httpClient.ts";

export function loginRequest(credentials: Credentials) {
  return httpRequest<TokenPayload>(env.authBaseUrl, "/api/users/login/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(credentials),
  });
}

export function refreshTokenRequest(refresh: string) {
  return httpRequest<TokenPayload>(
    env.authBaseUrl,
    "/api/users/token/refresh/",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    },
  );
}

export function meRequest(accessToken: string) {
  return httpRequest<AuthUserPayload>(env.authBaseUrl, "/api/users/me/", {
    method: "GET",
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}

export function logoutRequest(access: string, refresh: string) {
  return httpRequest(env.authBaseUrl, "/api/users/logout/", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${access}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ refresh }),
    keepalive: true,
  });
}
