"use client";

import { createContext, useContext, useEffect, useState, useCallback, ReactNode } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";

const API = process.env.NEXT_PUBLIC_API_URL || "";

// D-50: every protected route lives under /dashboard. Keep the predicate
// hoisted so the route-guard useEffect's dep array stays stable across renders.
function isProtectedPath(p: string): boolean {
  return p.startsWith('/dashboard');
}

interface User {
  id: string;
  email: string;
  display_name: string;
  avatar_url: string | null;
  role: string;
  tenant_id: string;
  tenant_name: string;
}

// D-49 / D-51 surfaceable login error: `.status` carries the HTTP code so /login
// can decide whether to swap in the generic 401 copy or pass-through `.message`.
export class AuthError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.name = 'AuthError';
    this.status = status;
  }
}

interface AuthState {
  user: User | null;
  loading: boolean;
  // D-49: throws AuthError with `.status` on credential failure (no router-side
  // navigation here — /login owns the post-success router.replace so it can
  // honor `?next=`).
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string) => Promise<string | null>;
  // D-51: throws Error with the user-facing copy when SSO is unreachable.
  loginSSO: (provider: 'google' | 'azure') => Promise<void>;
  logout: () => void;
  token: string | null;
}

const AuthContext = createContext<AuthState>({
  user: null, loading: true,
  login: async () => {},
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
  // D-D-09 / T-10-11 — clear the TanStack cache on logout so a subsequent
  // user on a shared machine can't see the previous user's cached data.
  // Safe to call useQueryClient() here because <Providers> mounts
  // QueryClientProvider at the root layout, above AuthProvider, on every route.
  const qc = useQueryClient();

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

  // Redirect to login if not authenticated. D-50: preserve where the user
  // tried to go via `?next=<encoded pathname+search>`. /login validates the
  // target via sanitizeNext() before honoring it (Pitfall 10 — open-redirect).
  useEffect(() => {
    if (!loading && !user && pathname && isProtectedPath(pathname)) {
      const search =
        typeof window !== 'undefined' ? window.location.search : '';
      const next = encodeURIComponent(pathname + search);
      router.replace(`/login?next=${next}`);
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

  const login = useCallback(async (email: string, password: string): Promise<void> => {
    // D-49: throw AuthError with `.status` so /login can map 401 → generic copy
    // and pass through other 4xx detail. The caller (LoginForm) owns the post-success
    // navigation so it can sanitize and honor `?next=` per D-50 + Pitfall 10.
    let resp: Response;
    try {
      resp = await fetch(`${API}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
    } catch (e: unknown) {
      // Network failure — surface as generic so error UI doesn't leak details.
      throw new AuthError('Sign-in failed. Try again in a moment.');
    }
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      throw new AuthError(data?.detail || 'Sign-in failed.', resp.status);
    }
    const data = await resp.json();
    storeTokens(data);
  }, []);

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

  // D-51: surface SSO failure via a thrown Error so /login can render the
  // D-51 verbatim copy in <ErrorAlert>. The backend's OIDC start endpoint is
  // a JSON GET that returns `{authorization_url, state}` — fetching it acts
  // as the "pre-flight" the plan describes; if it returns non-2xx (5xx, 503,
  // 404), or `authorization_url` is missing, we throw BEFORE navigating away.
  // Caller (SsoRow.handleSso) catches and pipes the message into setAuthError.
  const loginSSO = useCallback(async (provider: 'google' | 'azure') => {
    const provName = provider === 'google' ? 'Google' : 'Microsoft';
    const unavailable = `Sign-in with ${provName} is temporarily unavailable. Try email instead.`;
    let resp: Response;
    try {
      resp = await fetch(`${API}/auth/login/${provider}`);
    } catch {
      throw new Error(unavailable);
    }
    if (!resp.ok) {
      throw new Error(unavailable);
    }
    let data: { authorization_url?: string; state?: string };
    try {
      data = await resp.json();
    } catch {
      throw new Error(unavailable);
    }
    if (!data?.authorization_url) {
      throw new Error(unavailable);
    }
    if (data.state) {
      // Store state for callback (existing pattern preserved).
      localStorage.setItem("getvul_sso_state", data.state);
    }
    window.location.href = data.authorization_url;
  }, []);

  const logout = useCallback(() => {
    fetch(`${API}/auth/logout`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    }).catch(() => {});
    clearAuth();
    // D-D-09: drop the TanStack cache so the next user on a shared device
    // doesn't see this user's queried data. T-10-11 information-disclosure
    // mitigation. Called between clearAuth() and router.replace so the
    // /login render starts with an empty cache.
    qc.clear();
    router.replace("/login");
  }, [token, router, qc]);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, loginSSO, logout, token }}>
      {children}
    </AuthContext.Provider>
  );
}
