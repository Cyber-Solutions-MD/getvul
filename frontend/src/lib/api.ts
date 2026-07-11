const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

// Typed API error carrying the HTTP status + the Phase-07 X-Request-ID so
// downstream error UI (use-query-errors.ts → PartialFailureBanner) can render
// "HTTP <code> · Request ID <id>" for operator correlation. Throwing a bare
// Error dropped both (banner showed "HTTP unknown · Request ID unknown") and
// stringified object-valued `detail` to "[object Object]".
export class ApiError extends Error {
  code: number;
  requestId: string;
  constructor(message: string, code: number, requestId: string) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.requestId = requestId;
  }
}

// FastAPI puts the machine-readable payload under `detail`, which may be a
// string OR a structured object (e.g. {"reason": "password_change_required"}).
// Coerce to a human string without ever producing "[object Object]".
function extractDetailMessage(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null | undefined)?.detail;
  if (typeof detail === "string" && detail) return detail;
  if (detail && typeof detail === "object") {
    const d = detail as { reason?: unknown; message?: unknown };
    if (typeof d.message === "string" && d.message) return d.message;
    if (typeof d.reason === "string" && d.reason) return d.reason;
  }
  return `API error: ${status}`;
}

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
  // Phase 10 (D-D / RESEARCH Pattern 5): explicit AbortSignal pass-through so
  // TanStack Query can cancel in-flight fetches when a query unmounts or refetches.
  // Already inherited via RequestInit; annotated here for discoverability + grep.
  signal?: AbortSignal | null;
}

export async function api<T = any>(
  path: string,
  options: FetchOptions = {}
): Promise<T> {
  const { token, headers: customHeaders, signal, ...rest } = options;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token || getToken()}`,
    ...(customHeaders as Record<string, string>),
  };

  // Phase 10 / RESEARCH Pattern 5: signal pass-through is explicit so
  // TanStack Query can cancel both the initial fetch and the post-refresh retry.
  let res = await fetch(`${API_URL}${path}`, { headers, signal, ...rest });

  // Auto-refresh on 401.
  //
  // BL-06: restrict transparent retry to RFC 9110 §9.2.2 safe methods
  // (GET / HEAD / OPTIONS). Mutating methods (POST / PUT / PATCH / DELETE)
  // are not safely re-issuable: if the original request reached the server
  // and partially succeeded (e.g. snooze UPDATE committed but the response
  // 401'd from a downstream auth middleware), the silent retry would apply
  // the mutation a second time. Worse, on a shared machine where the user
  // logged out between request and retry, the refresh would mint a token
  // for a DIFFERENT user and the retry would log the audit event under the
  // wrong user (the IDOR filter saves us from cross-tenant data but the
  // audit attribution is corrupted — AUDIT-01).
  //
  // For mutations, surface the 401 to the caller so the mutation hook can
  // re-prompt or dispatch logout. The login redirect still happens for the
  // refresh-failed case (because in that case the user is logged out
  // regardless of method).
  if (res.status === 401 && !token) {
    const method = (rest.method ?? "GET").toUpperCase();
    const isSafeMethod = method === "GET" || method === "HEAD" || method === "OPTIONS";
    if (!isSafeMethod) {
      // Don't silently retry mutations — surface the auth failure. The
      // mutation hook can decide (re-prompt, dispatch logout, show toast).
      // Login redirect is intentionally NOT triggered here: a mutation
      // that 401s after the user already navigated (e.g. logout-in-flight)
      // shouldn't yank them out of the auth flow they're already in.
      throw new Error("Session expired during mutation. Please retry.");
    }
    const refreshed = await tryRefreshToken();
    if (refreshed) {
      headers.Authorization = `Bearer ${getToken()}`;
      res = await fetch(`${API_URL}${path}`, { headers, signal, ...rest });
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
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    const requestId = res.headers?.get("x-request-id") || "unknown";
    throw new ApiError(extractDetailMessage(body, res.status), res.status, requestId);
  }

  return res.json();
}

export { API_URL };
