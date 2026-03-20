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

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
