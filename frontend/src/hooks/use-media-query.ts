'use client';
import { useEffect, useState } from 'react';

// Used by Phase 11 to branch desktop drill panel ↔ vaul mobile bottom-sheet
// at the <900px breakpoint (D-P-03). SSR-safe: returns `false` on the
// server / first client render to avoid hydration mismatch; the actual
// value lands after mount via a synchronous matchMedia check.
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(false);
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    const mql = window.matchMedia(query);
    setMatches(mql.matches);
    const handler = (e: MediaQueryListEvent) => setMatches(e.matches);
    mql.addEventListener('change', handler);
    return () => mql.removeEventListener('change', handler);
  }, [query]);
  return matches;
}
