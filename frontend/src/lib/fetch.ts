/**
 * Get auth headers for raw fetch() calls.
 * Returns fresh headers each call (reads token from localStorage).
 */
export function getAuthHeaders(): Record<string, string> {
  const token = typeof window !== "undefined"
    ? localStorage.getItem("getvul_token") || "dev-token"
    : "dev-token";
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
}

/**
 * Wrapper for fetch that auto-redirects to login on 401.
 */
export async function authedFetch(url: string, options?: RequestInit): Promise<Response> {
  const resp = await fetch(url, { ...options, headers: { ...getAuthHeaders(), ...(options?.headers || {}) } });
  if (resp.status === 401 && typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
    localStorage.removeItem("getvul_token");
    localStorage.removeItem("getvul_refresh");
    window.location.href = "/login";
  }
  return resp;
}

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

/**
 * Proxy object that lazily computes headers on property access.
 * Use this for module-level `const headers = lazyHeaders;` declarations.
 */
export const lazyHeaders = new Proxy({} as Record<string, string>, {
  get(_, prop: string) {
    return getAuthHeaders()[prop];
  },
  ownKeys() {
    return Object.keys(getAuthHeaders());
  },
  getOwnPropertyDescriptor(_, prop: string) {
    const h = getAuthHeaders();
    if (prop in h) return { configurable: true, enumerable: true, value: h[prop] };
    return undefined;
  },
});
