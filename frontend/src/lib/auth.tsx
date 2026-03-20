"use client";

import { createContext, useContext, useEffect, useState, useCallback, ReactNode } from "react";
import { useRouter, usePathname } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface User {
  id: string;
  email: string;
  display_name: string;
  avatar_url: string | null;
  role: string;
  tenant_id: string;
  tenant_name: string;
}

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<string | null>;
  register: (email: string, password: string, name: string) => Promise<string | null>;
  loginSSO: (provider: string) => Promise<void>;
  logout: () => void;
  token: string | null;
}

const AuthContext = createContext<AuthState>({
  user: null, loading: true,
  login: async () => null,
  register: async () => null,
  loginSSO: async () => {},
  logout: () => {},
  token: null,
});

export function useAuth() { return useContext(AuthContext); }

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  // Load token from storage on mount
  useEffect(() => {
    const stored = localStorage.getItem("getvul_token");
    const storedRefresh = localStorage.getItem("getvul_refresh");
    if (stored) {
      setToken(stored);
      fetchMe(stored).then(u => {
        if (u) setUser(u);
        else {
          // Try refresh
          if (storedRefresh) {
            refreshToken(storedRefresh).then(ok => {
              if (!ok) clearAuth();
            });
          } else {
            clearAuth();
          }
        }
        setLoading(false);
      });
    } else {
      setLoading(false);
    }
  }, []);

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!loading && !user && pathname?.startsWith("/dashboard")) {
      router.replace("/login");
    }
  }, [loading, user, pathname, router]);

  async function fetchMe(t: string): Promise<User | null> {
    try {
      const resp = await fetch(`${API}/auth/me`, {
        headers: { Authorization: `Bearer ${t}` },
      });
      if (resp.ok) return await resp.json();
    } catch {}
    return null;
  }

  async function refreshToken(refresh: string): Promise<boolean> {
    try {
      const resp = await fetch(`${API}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refresh }),
      });
      if (resp.ok) {
        const data = await resp.json();
        const newToken = data.access_token;
        localStorage.setItem("getvul_token", newToken);
        setToken(newToken);
        const u = await fetchMe(newToken);
        if (u) { setUser(u); return true; }
      }
    } catch {}
    return false;
  }

  function storeTokens(data: any) {
    localStorage.setItem("getvul_token", data.access_token);
    if (data.refresh_token) localStorage.setItem("getvul_refresh", data.refresh_token);
    setToken(data.access_token);
    if (data.user) setUser(data.user);
  }

  function clearAuth() {
    localStorage.removeItem("getvul_token");
    localStorage.removeItem("getvul_refresh");
    setToken(null);
    setUser(null);
  }

  const login = useCallback(async (email: string, password: string): Promise<string | null> => {
    try {
      const resp = await fetch(`${API}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await resp.json();
      if (!resp.ok) return data.detail || "Login failed";
      storeTokens(data);
      router.replace("/dashboard");
      return null;
    } catch (e: any) {
      return e.message || "Connection error";
    }
  }, [router]);

  const register = useCallback(async (email: string, password: string, name: string): Promise<string | null> => {
    try {
      const resp = await fetch(`${API}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, display_name: name }),
      });
      const data = await resp.json();
      if (!resp.ok) return data.detail || "Registration failed";
      storeTokens(data);
      router.replace("/dashboard");
      return null;
    } catch (e: any) {
      return e.message || "Connection error";
    }
  }, [router]);

  const loginSSO = useCallback(async (provider: string) => {
    try {
      const resp = await fetch(`${API}/auth/login/${provider}`);
      const data = await resp.json();
      if (data.authorization_url) {
        // Store state for callback
        localStorage.setItem("getvul_sso_state", data.state);
        window.location.href = data.authorization_url;
      }
    } catch {}
  }, []);

  const logout = useCallback(() => {
    fetch(`${API}/auth/logout`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    }).catch(() => {});
    clearAuth();
    router.replace("/login");
  }, [token, router]);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, loginSSO, logout, token }}>
      {children}
    </AuthContext.Provider>
  );
}
