import { clearSession, getToken } from "./session";

export const AUTH_EXPIRED_EVENT = "receptionist:auth-expired";

export function notifyAuthExpired(): void {
  if (typeof window === "undefined") return;
  clearSession();
  window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
}
