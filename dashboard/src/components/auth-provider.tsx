"use client";

import { usePathname, useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { api } from "@/lib/api-client";
import type { Clinic, LoginResponse, Staff } from "@/lib/api-types";
import { AUTH_EXPIRED_EVENT } from "@/lib/auth-events";
import { getErrorMessage } from "@/lib/errors";
import {
  clearSession,
  clearSetupSkip,
  getSession,
  saveSession,
} from "@/lib/session";

type AuthContextValue = {
  staff: Staff | null;
  clinic: Clinic | null;
  loading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  establishSession: (response: LoginResponse) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
  setClinic: (clinic: Clinic) => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const isPublicPath = pathname === "/" || pathname === "/login";
  const [staff, setStaff] = useState<Staff | null>(null);
  const [clinic, setClinic] = useState<Clinic | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const stored = getSession();
    if (!stored) {
      setStaff(null);
      setClinic(null);
      setLoading(false);
      return;
    }

    try {
      const [currentStaff, currentClinic] = await Promise.all([
        api.me(),
        api.getClinic(),
      ]);
      setStaff(currentStaff);
      setClinic(currentClinic);
      saveSession({ token: stored.token, staff: currentStaff });
      setError(null);
    } catch (caught) {
      clearSession();
      setStaff(null);
      setClinic(null);
      setError(getErrorMessage(caught));
      if (!isPublicPath) {
        router.replace("/login");
      }
    } finally {
      setLoading(false);
    }
  }, [isPublicPath, router]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    function handleExpired() {
      clearSetupSkip();
      setStaff(null);
      setClinic(null);
      setLoading(false);
      if (!isPublicPath) {
        router.replace("/login");
      }
    }

    window.addEventListener(AUTH_EXPIRED_EVENT, handleExpired);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, handleExpired);
  }, [isPublicPath, router]);

  const establishSession = useCallback(async (response: LoginResponse) => {
    clearSetupSkip();
    saveSession({ token: response.access_token, staff: response.staff });

    try {
      const currentClinic = await api.getClinic();
      setStaff(response.staff);
      setClinic(currentClinic);
      setError(null);
    } catch (caught) {
      clearSession();
      setStaff(null);
      setClinic(null);
      throw caught;
    }
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const response = await api.login({ email, password });
      await establishSession(response);
    },
    [establishSession],
  );

  const logout = useCallback(() => {
    clearSession();
    clearSetupSkip();
    setStaff(null);
    setClinic(null);
    router.replace("/login");
  }, [router]);

  const value = useMemo(
    () => ({
      staff,
      clinic,
      loading,
      error,
      login,
      establishSession,
      logout,
      refresh: load,
      setClinic,
    }),
    [staff, clinic, loading, error, login, establishSession, logout, load],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider.");
  }
  return context;
}
