import { NextResponse, type NextRequest } from 'next/server';

// Legacy URL redirects (Open Question 2, D-34).
// Wave 2's vertical-slice work consolidates the five top-level routes
// (/assets, /integrations, /settings, /tickets, /vulnerabilities) under the
// /dashboard/* shell. This middleware preserves old bookmarks with a 308
// (permanent + method-preserving) redirect so existing browser histories,
// Slack links, and Jira backlinks keep working.
//
// NOTE: this middleware does NOT do auth gating. The route guard lives in
// useAuth() (lib/auth.tsx) and runs client-side because tokens are stored
// in localStorage, not cookies — middleware (which sees only the request
// envelope) can't read localStorage. See research §Pattern 5.
const LEGACY_MAP: Record<string, string> = {
  '/assets':          '/dashboard/assets',
  '/integrations':    '/dashboard/integrations',
  '/settings':        '/dashboard/settings',
  '/tickets':         '/dashboard/tickets',
  '/vulnerabilities': '/dashboard/vulnerabilities',
};

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Exact root match (e.g. /assets → /dashboard/assets)
  if (LEGACY_MAP[pathname]) {
    const url = request.nextUrl.clone();
    url.pathname = LEGACY_MAP[pathname];
    return NextResponse.redirect(url, 308);
  }

  // Subpath match (e.g. /assets/abc123 → /dashboard/assets/abc123)
  for (const [legacy, canonical] of Object.entries(LEGACY_MAP)) {
    if (pathname.startsWith(legacy + '/')) {
      const url = request.nextUrl.clone();
      url.pathname = canonical + pathname.slice(legacy.length);
      return NextResponse.redirect(url, 308);
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    '/assets/:path*',
    '/integrations/:path*',
    '/settings/:path*',
    '/tickets/:path*',
    '/vulnerabilities/:path*',
  ],
};
