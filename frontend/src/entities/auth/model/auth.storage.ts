import { readJsonStorage, writeJsonStorage } from "@/shared/lib/storage.ts";
import type { AuthSession } from "./types.ts";

const AUTH_STORAGE_KEY = "blandskron.auth";

export function loadAuthSession() {
  return readJsonStorage<AuthSession | null>(AUTH_STORAGE_KEY, null);
}

export function saveAuthSession(auth: AuthSession) {
  writeJsonStorage(AUTH_STORAGE_KEY, auth);
}

export function clearAuthSession() {
  localStorage.removeItem(AUTH_STORAGE_KEY);
}
