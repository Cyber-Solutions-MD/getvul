'use client';
// BL-05: thin client wrapper around `next/dynamic({ ssr: false })`. Lives
// here (rather than inline in page.tsx) because:
//   - `next/dynamic({ ssr: false })` is only valid in client components in
//     Next 15 — server components throw at build time.
//   - The production server-component shell (`page.tsx`) does `notFound()`
//     before referencing this loader, so the showcase chunk is unreachable
//     from the prod entry and is dropped from the production bundle.
import dynamic from 'next/dynamic';

const PrimitivesShowcase = dynamic(() => import('./showcase'), {
  ssr: false,
  loading: () => <div aria-busy="true" className="min-h-screen bg-bg" />,
});

export function ShowcaseClientLoader() {
  return <PrimitivesShowcase />;
}
