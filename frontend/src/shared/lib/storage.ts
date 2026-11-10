export function readJsonStorage<T>(key: string, fallback: T): T {
  try {
    const value = JSON.parse(localStorage.getItem(key) || "null");
    return value ?? fallback;
  } catch {
    return fallback;
  }
}

export function writeJsonStorage(key: string, value: unknown) {
  localStorage.setItem(key, JSON.stringify(value));
}
