import type { ApiClient, MaybeClient } from "@/shared/api/types.ts";
import {
  connectGoogleDrive,
  getGoogleDriveAuthUrl,
} from "./api/google-drive-import.api.ts";
import type { DriveConnection } from "./types.ts";

const storageKey = "blandskron.drive.oauth.v1";
const ttl = 5 * 60 * 1000;
const pending = new WeakMap<ApiClient, Promise<DriveConnection>>();
const base64url = (bytes: Uint8Array) =>
  btoa(String.fromCharCode(...bytes))
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replaceAll("=", "");
const fail = () =>
  new Error(
    "La autorización de Drive no corresponde a esta sesión o expiró. Inicia la conexión nuevamente.",
  );

export async function startDriveAuthorization(
  client: MaybeClient,
  scope: string | null,
  browser = window,
  isCurrent = () => true,
) {
  if (!scope || !browser.crypto?.subtle) throw fail();
  if (!client) throw fail();
  pending.delete(client);
  const verifier = base64url(
    browser.crypto.getRandomValues(new Uint8Array(32)),
  );
  const challenge = base64url(
    new Uint8Array(
      await browser.crypto.subtle.digest(
        "SHA-256",
        new TextEncoder().encode(verifier),
      ),
    ),
  );
  const payload = await getGoogleDriveAuthUrl(client, challenge);
  if (!isCurrent()) throw new DOMException("La conexión cambió.", "AbortError");
  const authorization = new URL(payload.authorization_url);
  const redirect = new URL(payload.redirect_uri);
  if (
    authorization.origin !== "https://accounts.google.com" ||
    authorization.pathname !== "/o/oauth2/v2/auth" ||
    !/^[A-Za-z0-9_-]{43}$/.test(payload.state) ||
    authorization.searchParams.get("state") !== payload.state ||
    authorization.searchParams.get("code_challenge") !== challenge ||
    authorization.searchParams.get("code_challenge_method") !== "S256" ||
    authorization.searchParams.get("redirect_uri") !== redirect.href ||
    redirect.origin !== browser.location.origin ||
    !["/documents", "/applications/google-drive"].includes(redirect.pathname)
  )
    throw fail();
  browser.sessionStorage.setItem(
    storageKey,
    JSON.stringify({
      scope,
      state: payload.state,
      verifier,
      createdAt: Date.now(),
      callbackPath: redirect.pathname,
    }),
  );
  browser.location.assign(authorization.href);
}

export function completeDriveAuthorization(
  client: MaybeClient,
  scope: string | null,
  browser = window,
) {
  if (!client) return null;
  const url = new URL(browser.location.href);
  const params = url.searchParams;
  const fields = [
    "code",
    "state",
    "error",
    "error_description",
    "error_uri",
    "scope",
    "authuser",
    "prompt",
    "iss",
  ];
  const isCallback = ["code", "state", "error"].some((name) =>
    params.has(name),
  );
  if (!isCallback) return pending.get(client) || null;
  const duplicate = fields.some((name) => params.getAll(name).length > 1);
  const values = Object.fromEntries(params);
  fields.forEach((name) => url.searchParams.delete(name));
  browser.history.replaceState(
    {},
    "",
    `${url.pathname}${url.search}${url.hash}`,
  );
  let attempt: {
    scope: string;
    state: string;
    verifier: string;
    createdAt: number;
    callbackPath: string;
  } | null = null;
  try {
    attempt = JSON.parse(browser.sessionStorage.getItem(storageKey) || "null");
  } catch {
    /* invalid local attempt */
  }
  browser.sessionStorage.removeItem(storageKey);
  // Cache the whole outcome before React StrictMode can mount the callback again.
  const task = Promise.resolve().then(() => {
    if (
      duplicate ||
      !scope ||
      !attempt ||
      attempt.scope !== scope ||
      attempt.state !== values.state ||
      attempt.callbackPath !== url.pathname ||
      Date.now() - attempt.createdAt > ttl ||
      Date.now() < attempt.createdAt ||
      !/^[A-Za-z0-9_-]{43}$/.test(attempt.verifier) ||
      !values.code ||
      values.error ||
      (values.iss && values.iss !== "https://accounts.google.com")
    )
      throw fail();
    return connectGoogleDrive(client, {
      code: values.code,
      state: values.state,
      code_verifier: attempt.verifier,
      ...(values.iss ? { issuer: values.iss } : {}),
    });
  });
  pending.set(client, task);
  return task;
}

export function clearDriveCallback(
  client: MaybeClient,
  task?: Promise<DriveConnection>,
) {
  if (client && (!task || pending.get(client) === task)) pending.delete(client);
}
