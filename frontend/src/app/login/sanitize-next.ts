// Open-redirect sanitizer (Pitfall 10, T-09-05-01) for /login `?next=` redirects.
//
// Lifted out of page.tsx into a sibling module because Next.js 15 enforces a
// closed set of page-file exports (default + route-segment config like
// `revalidate`, `dynamic`, etc.) — adding `export function sanitizeNext` to
// page.tsx fails the build with: `"sanitizeNext" is not a valid Page export
// field.` This file lets the test suite import the function in isolation.
//
// Same-origin relative paths only — anything else falls back to /dashboard.
export function sanitizeNext(raw: string | null): string {
  if (!raw) return '/dashboard';
  let decoded: string;
  try {
    decoded = decodeURIComponent(raw);
  } catch {
    return '/dashboard';
  }
  // Must start with `/` AND not start with `//` (protocol-relative) or `/\`
  // (Windows path tricks like /\evil.com that some routers normalize away).
  if (
    decoded.startsWith('/') &&
    !decoded.startsWith('//') &&
    !decoded.startsWith('/\\')
  ) {
    return decoded;
  }
  return '/dashboard';
}
