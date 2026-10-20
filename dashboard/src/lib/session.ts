const STORAGE_KEY = "ai-receptionist-session";

export type StoredSession = {
  token: string;
  staff: import("./api-types").Staff;
};

export function getSession(): StoredSession | null {
  if (typeof window === "undefined") return null;

  const raw = window.sessionStorage.getItem(STORAGE_KEY);
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw) as Partial<StoredSession>;
    if (!parsed.token || !parsed.staff) {
      clearSession();
      return null;
    }
    return parsed as StoredSession;
  } catch {
    clearSession();
    return null;
  }
}

export function getToken(): string | null {
  return getSession()?.token ?? null;
}

export function saveSession(session: StoredSession): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

export function clearSession(): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(STORAGE_KEY);
}

export const SETUP_SKIPPED_KEY = "ai-receptionist-setup-skipped";

export function isSetupSkipped(): boolean {
  if (typeof window === "undefined") return false;
  return window.sessionStorage.getItem(SETUP_SKIPPED_KEY) === "true";
}

export function skipSetupForSession(): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(SETUP_SKIPPED_KEY, "true");
}

export function clearSetupSkip(): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(SETUP_SKIPPED_KEY);
}
