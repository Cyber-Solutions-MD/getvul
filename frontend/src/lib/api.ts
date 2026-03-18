const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Dev token for local development (bypasses SSO)
const DEV_TOKEN = "dev-token";

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
    Authorization: `Bearer ${token || DEV_TOKEN}`,
    ...(customHeaders as Record<string, string>),
  };

  const res = await fetch(`${API_URL}${path}`, {
    headers,
    ...rest,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `API error: ${res.status}`);
  }

  return res.json();
}

export { API_URL, DEV_TOKEN };
