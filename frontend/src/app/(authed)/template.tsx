'use client';
import { useLayoutEffect, useState } from 'react';
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
// The wrapper div gets className="authed-page-content" (block element, no display:contents):
//   - "authed-page-content": receives view-transition-name from globals.css, isolating
//     the content snapshot from the root (sidebar+topbar stay static, D-05).
//   - WR-01 fix: display:contents was removed. An element with display:contents generates
//     no principal box — the browser has nothing to capture for the named VT group, causing
//     a silent fallback to the root snapshot (whole viewport incl. sidebar/topbar fades,
//     violating D-05). Removing `contents` gives the wrapper a real block box.
//     Layout-safety confirmed: the parent <main> in AppShell (app-shell.tsx:37) is a plain
//     block container with no flex/grid parent on the content slot, so a block-level child
//     here introduces no layout shift.
//
// view-transition-name is applied via the CSS class (globals.css), NOT inline style — avoids
// the inline-style hydration concern (A3).
//
// D-07/D-08 first-mount guard: template.tsx remounts on EVERY pathname change, so a
// useRef(true) guard would reset every navigation (each remount gets a fresh ref). A
// module-level boolean correctly survives React remounts but resets on hard refresh /
// full page reload — exactly what D-07/D-08 require (no fade on first paint/entry).
// Named isFirstMount to match the plan's D-07/D-08 guard contract.
let isFirstMount = true;

export default function AuthedTemplate({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  // IN-03 fix: gate the no-VT fallback (data-no-vt) behind non-first-mount so that
  // Firefox/no-VT browsers do NOT get a fade-in on the initial page paint (D-07/D-08).
  // State initializes to false on both server and first client render; the effect sets
  // it to true after the first mount so subsequent navigations activate the fallback CSS.
  const [pastFirstMount, setPastFirstMount] = useState(false);

  useLayoutEffect(() => {
    // D-07/D-08: no fade on first paint / hard refresh / app entry.
    // isFirstMount (module-level) is true on the first load; subsequent navigation-driven
    // remounts find it false and proceed to startViewTransition.
    if (isFirstMount) {
      isFirstMount = false;
      // Mark as past first mount so the no-VT CSS fallback activates on next navigation.
      setPastFirstMount(true);
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

  // Feature-detect for the CSS fallback. Only activated after the first mount (pastFirstMount)
  // so the initial page paint never fades on no-VT browsers (IN-03 / D-07/D-08).
  const noVt =
    pastFirstMount &&
    typeof document !== 'undefined' &&
    !('startViewTransition' in document);

  return (
    <div className="authed-page-content" {...(noVt ? { 'data-no-vt': '' } : {})}>
      {children}
    </div>
  );
}
