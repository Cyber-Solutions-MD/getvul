'use client';
/**
 * useLens — RPT-02 (Phase 43 Plan 04, D-05/D-06). The dashboard lens is a
 * job-function VIEW (analyst / it-ops / compliance / leadership), decoupled
 * from the RBAC role tier (T-43-13 — lens selection never gates on nor
 * grants role; it is presentation-only).
 *
 * Mirrors `useUrlState`'s URL-is-source-of-truth idiom (Phase 42's
 * `?range=`/`?window=` pattern) but adds a `localStorage` dual-persistence
 * layer that `useUrlState` itself does NOT provide (43-PATTERNS.md
 * "localStorage-fallback note" — genuinely new plumbing, not a
 * re-derivation of an existing hook):
 *
 *   - An explicit `?lens=` URL param always wins (deep-linkable, e.g. the
 *     framework-posture-strip's `/dashboard?lens=leadership` links).
 *   - Absent that, a bare `/dashboard` visit falls back to whatever lens
 *     was last written to `localStorage` (a real React state slice, not a
 *     derived read, so the seeded value renders on the SAME initial paint
 *     rather than only after a URL round-trip).
 *   - `setLens` writes BOTH localStorage and the URL (`router.replace`),
 *     mirroring `useUrlState`'s own delete-on-default / set-otherwise
 *     convention so the URL never carries a redundant `?lens=analyst`.
 *
 * Default lens: `analyst` (zero disruption to the already-shipped
 * dashboard — D-05).
 */
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useState } from 'react';

export type Lens = 'analyst' | 'it-ops' | 'compliance' | 'leadership';

export const ALLOWED_LENSES: readonly Lens[] = ['analyst', 'it-ops', 'compliance', 'leadership'] as const;

const STORAGE_KEY = 'dashboard-lens';
const DEFAULT_LENS: Lens = 'analyst';

function isLens(value: string | null | undefined): value is Lens {
  return value != null && (ALLOWED_LENSES as readonly string[]).includes(value);
}

export function useLens(): [Lens, (next: Lens) => void] {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const rawParam = params?.get('lens') ?? null;

  // Seeded once from localStorage on mount (bare `/dashboard` visit, no
  // `?lens=` param). A real state slice — not a derived read — so the
  // seeded lens is reflected on the FIRST render that has it available,
  // and so `setLens` below can update it optimistically even in
  // environments where `router.replace` doesn't actually mutate
  // `useSearchParams` synchronously (e.g. this hook's own unit tests).
  const [storedFallback, setStoredFallback] = useState<Lens | null>(null);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (isLens(stored)) setStoredFallback(stored);
    // Mount-only seed — an explicit ?lens= param (checked below) always
    // takes precedence over whatever this effect finds regardless.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const lens: Lens = isLens(rawParam) ? rawParam : (storedFallback ?? DEFAULT_LENS);

  const setLens = (next: Lens) => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(STORAGE_KEY, next);
    }
    setStoredFallback(next);

    const sp = new URLSearchParams(params?.toString() ?? '');
    if (next === DEFAULT_LENS) sp.delete('lens');
    else sp.set('lens', next);
    const qs = sp.toString();
    const target = qs ? `${pathname}?${qs}` : (pathname ?? '/');
    router.replace(target, { scroll: false });
  };

  return [lens, setLens];
}
