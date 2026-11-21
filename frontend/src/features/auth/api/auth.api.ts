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

export function readCsrfToken(
  cookieSource: string = typeof document !== "undefined" ? document.cookie : "",
): string | null {
  const match = cookieSource
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith("csrftoken="));
  return match ? decodeURIComponent(match.slice("csrftoken=".length)) : null;
}

export function cookieLoginRequest(
  credentials: Credentials,
  csrfToken: string | null = readCsrfToken(),
) {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (csrfToken) headers["X-CSRFToken"] = csrfToken;
  return httpRequest<{ status: string }>(
    env.authBaseUrl,
    "/api/users/session/login/",
    {
      method: "POST",
      credentials: "include",
      headers,
      body: JSON.stringify(credentials),
    },
  );
}

export function cookieRefreshRequest(
  csrfToken: string | null = readCsrfToken(),
) {
  const headers: Record<string, string> = {};
  if (csrfToken) headers["X-CSRFToken"] = csrfToken;
  return httpRequest<{ status: string }>(
    env.authBaseUrl,
    "/api/users/session/refresh/",
    {
      method: "POST",
      credentials: "include",
      headers,
    },
  );
}

export function cookieLogoutRequest(
  csrfToken: string | null = readCsrfToken(),
) {
  const headers: Record<string, string> = {};
  if (csrfToken) headers["X-CSRFToken"] = csrfToken;
  return httpRequest<{ status: string }>(
    env.authBaseUrl,
    "/api/users/session/logout/",
    {
      method: "POST",
      credentials: "include",
      headers,
      keepalive: true,
    },
  );
}

export interface SetupStatusPayload {
  needs_setup: boolean;
  google_login_enabled: boolean;
  google_client_id: string | null;
  smtp_configured: boolean;
}

export interface RegisterPayload {
  email: string;
  password: string;
  username?: string;
  first_name?: string;
  last_name?: string;
  workspace_name?: string;
}

export function setupStatusRequest() {
  return httpRequest<SetupStatusPayload>(
    env.authBaseUrl,
    "/api/users/setup-status/",
    { method: "GET" },
  );
}

export function registerRequest(payload: RegisterPayload) {
  return httpRequest<TokenPayload & { is_initial_admin?: boolean }>(
    env.authBaseUrl,
    "/api/users/register/",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}

export function passwordResetRequest(email: string) {
  return httpRequest<{ status?: string; code?: string; detail: string }>(
    env.authBaseUrl,
    "/api/users/password-reset/request/",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    },
  );
}

export function googleOidcLoginRequest(
  idToken: string,
  options: { nonce?: string; redirectUri?: string } = {},
) {
  return httpRequest<TokenPayload & { created?: boolean }>(
    env.authBaseUrl,
    "/api/users/google/login/",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id_token: idToken,
        nonce: options.nonce || "",
        redirect_uri: options.redirectUri || "",
      }),
    },
  );
}
