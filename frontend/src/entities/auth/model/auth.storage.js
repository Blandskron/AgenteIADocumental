import { readJsonStorage, writeJsonStorage } from "../../../shared/lib/storage";

const AUTH_STORAGE_KEY = "blandskron.auth";

export function loadAuthSession() {
  return readJsonStorage(AUTH_STORAGE_KEY, null);
}

export function saveAuthSession(auth) {
  writeJsonStorage(AUTH_STORAGE_KEY, auth);
}

export function clearAuthSession() {
  localStorage.removeItem(AUTH_STORAGE_KEY);
}
