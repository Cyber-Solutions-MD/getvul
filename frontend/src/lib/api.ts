const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken(): string {
  if (typeof window !== "undefined") {
    return localStorage.getItem("getvul_token") || "dev-token";
  }
  return "dev-token";
}

async function tryRefreshToken(): Promise<boolean> {
  if (typeof window === "undefined") return false;
  const refresh = localStorage.getItem("getvul_refresh");
  if (!refresh) return false;

  try {
    const resp = await fetch(`${API_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (resp.ok) {
      const data = await resp.json();
      localStorage.setItem("getvul_token", data.access_token);
      return true;
    }
  } catch {}
  return false;
}

interface FetchOptions extends RequestInit {
  token?: string;
}

export async function api<T = any>(
  path: string,
  options: FetchOptions = {}
): Promise<T> {
  const { token, headers: customHeaders, ...rest } = options;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token || getToken()}`,
    ...(customHeaders as Record<string, string>),
  };

  let res = await fetch(`${API_URL}${path}`, { headers, ...rest });

  // Auto-refresh on 401
  if (res.status === 401 && !token) {
    const refreshed = await tryRefreshToken();
    if (refreshed) {
      headers.Authorization = `Bearer ${getToken()}`;
      res = await fetch(`${API_URL}${path}`, { headers, ...rest });
    } else {
      // Refresh failed — redirect to login
      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
        localStorage.removeItem("getvul_token");
        localStorage.removeItem("getvul_refresh");
        window.location.href = "/login";
      }
      throw new Error("Session expired. Please login again.");
    }
  }

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `API error: ${res.status}`);
  }

  return res.json();
}

export { API_URL };
