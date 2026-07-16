'use client';
import { useLayoutEffect, useRef } from 'react';
import { usePathname } from 'next/navigation';
import type { ReactNode } from 'react';

// Phase 17 — Page-transition motion (UX-D-06-01..05).
//
// Next.js nests template.tsx BETWEEN layout.tsx and its children:
//   <AuthedLayout>  ← AppShell (sidebar+topbar+bottom-nav) MOUNTED ONCE, never fades
//     <Template>    ← this file — REMOUNTS on pathname (segment) change only (D-01/D-02)
//       {children}  ← route page
//     </Template>
//   </AuthedLayout>
//
// searchParams-only changes (DrillPanel ?drill=, tabs, list/board toggle) do NOT remount
// template.tsx — guaranteed by Next.js spec. No special handling needed (D-02/UX-D-06-04).
//
// The wrapper div gets className="authed-page-content contents":
//   - "authed-page-content": receives view-transition-name from globals.css, isolating
//     the content snapshot from the root (sidebar+topbar stay static, D-05).
//   - "contents": display:contents — transparent to flex/grid layout so no route shifts (A2).
//
// view-transition-name is applied via the CSS class (globals.css), NOT inline style — avoids
// the inline-style hydration concern (A3).

export default function AuthedTemplate({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const isFirstMount = useRef(true);

  useLayoutEffect(() => {
    // D-07/D-08: no fade on first paint / hard refresh / app entry.
    if (isFirstMount.current) {
      isFirstMount.current = false;
      return;
    }
    // D-06/UX-D-06-03: browsers without VT fall back to the CSS keyframe (data-no-vt).
    if (typeof document === 'undefined' || !document.startViewTransition) return;
    // Fires before paint so the browser captures the outgoing snapshot (Pitfall 2).
    // No update callback — React has already committed the new DOM on remount.
    document.startViewTransition();
    // pathname in deps documents intent; template already remounts per segment,
    // so this effect runs fresh each pathname change.
  }, [pathname]);

  // Feature-detect for the CSS fallback. Determined once on the client; used as a
  // data attribute below (client-only guard avoids the hydration mismatch, Assumption A3).
  const noVt =
    typeof document !== 'undefined' && !('startViewTransition' in document);

  return (
    <div className="authed-page-content contents" {...(noVt ? { 'data-no-vt': '' } : {})}>
      {children}
    </div>
  );
}
