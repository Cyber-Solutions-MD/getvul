// BL-05: server-component shell. Production builds 404 here before any
// client child is referenced, so the heavy primitives showcase
// (`./showcase`: lucide icons + Bomb / Section / Row demo) is not pulled
// into the production bundle.
//
// The previous shape was a single client component file with a runtime
// NODE_ENV guard at the top. Next.js doesn't tree-shake on runtime gates:
// even though the route 404'd at request time, every top-level import in
// page.tsx (lucide-react icons, the demo components) was still bundled
// and shipped.
//
// New shape:
//   - This file is a server component (no 'use client'). The NODE_ENV
//     branch is evaluated at build time — Next statically replaces
//     `process.env.NODE_ENV`, so in production the function body reduces
//     to `notFound()` and the dev branch is unreachable.
//   - The dev-only loader is referenced via a dev-gated dynamic
//     `import()` rather than a top-level static import. Static imports
//     are always bundled regardless of which branch references them;
//     dynamic `import()` produces a separate chunk that the prod entry
//     never requests because the gating branch is dead-code-eliminated.
//   - `./showcase-client-loader` then uses `next/dynamic({ ssr: false })`
//     internally to further code-split the heavy `./showcase` module
//     (server components cannot use `ssr: false` directly).
import { notFound } from 'next/navigation';
import { Suspense, lazy } from 'react';

// Dev-only lazy import. In production, `process.env.NODE_ENV === 'production'`
// is statically true so the ternary collapses to `null` and the dynamic
// `import()` is removed from the prod module graph entirely (Next's
// webpack does this DCE for statically resolvable conditions).
const ShowcaseClientLoader =
  process.env.NODE_ENV === 'production'
    ? null
    : lazy(() =>
        import('./showcase-client-loader').then((m) => ({
          default: m.ShowcaseClientLoader,
        })),
      );

export default function DevPrimitivesPage() {
  // D-31 + Open Question 6: production builds 404. The check happens on
  // the server side at module top so the showcase is never rendered or
  // requested by the client in prod.
  if (process.env.NODE_ENV === 'production' || !ShowcaseClientLoader) {
    notFound();
  }

  return (
    <Suspense fallback={<div aria-busy="true" className="min-h-screen bg-bg" />}>
      <ShowcaseClientLoader />
    </Suspense>
  );
}
