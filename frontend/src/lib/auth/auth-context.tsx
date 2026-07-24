import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { authApi, configureApi } from "@/lib/api/client";
import type { User } from "@/lib/api/types";
import { activityStore } from "@/lib/session/activity-store";

type AuthState = {
  user: User | null;
  token: string | null;
  expiresAt: number | null;
  status: "loading" | "authenticated" | "unauthenticated";
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthCtx = createContext<AuthState | null>(null);
const STORAGE_KEY = "medvault.session";

type Persisted = { token: string; expires_at: number; user: User };

function readSession(): Persisted | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const p = JSON.parse(raw) as Persisted;
    if (!p.token || !p.expires_at || p.expires_at < Date.now()) return null;
    return p;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [expiresAt, setExpiresAt] = useState<number | null>(null);
  const [status, setStatus] = useState<AuthState["status"]>("loading");

  const logout = useCallback(() => {
    if (typeof window !== "undefined") {
      sessionStorage.removeItem(STORAGE_KEY);
      activityStore.clear();
    }
    void queryClient.cancelQueries();
    queryClient.clear();
    setUser(null);
    setToken(null);
    setExpiresAt(null);
    setStatus("unauthenticated");
  }, [queryClient]);

  // Configure api client once
  useEffect(() => {
    configureApi({ getToken: () => token, onUnauthorized: () => logout() });
  }, [token, logout]);

  // Restore session
  useEffect(() => {
    const p = readSession();
    if (!p) {
      activityStore.clear();
      queryClient.clear();
      setStatus("unauthenticated");
      return;
    }
    setToken(p.token);
    setExpiresAt(p.expires_at);
    setUser(p.user);
    // Validate token
    configureApi({ getToken: () => p.token, onUnauthorized: () => logout() });
    authApi
      .me()
      .then((u) => {
        setUser(u);
        setStatus("authenticated");
      })
      .catch(() => logout());
  }, [logout, queryClient]);

  // Expiry watchdog
  useEffect(() => {
    if (!expiresAt) return;
    const ms = expiresAt - Date.now();
    if (ms <= 0) {
      logout();
      return;
    }
    const t = setTimeout(logout, ms);
    return () => clearTimeout(t);
  }, [expiresAt, logout]);

  const login = useCallback(async (email: string, password: string) => {
    const r = await authApi.login(email, password);
    const exp = Date.now() + r.expires_in * 1000;
    const p: Persisted = { token: r.access_token, expires_at: exp, user: r.user };
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(p));
    setToken(r.access_token);
    setExpiresAt(exp);
    setUser(r.user);
    setStatus("authenticated");
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    await authApi.register(email, password);
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      user,
      token,
      expiresAt,
      status,
      login,
      register,
      logout,
    }),
    [user, token, expiresAt, status, login, register, logout],
  );

  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthCtx);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
