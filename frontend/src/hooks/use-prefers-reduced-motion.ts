// usePrefersReducedMotion — listens to (prefers-reduced-motion: reduce).
//
// Stub created by Plan 10-04 because Plan 10-02 (wave-0 dependency) has not
// yet landed on this worktree branch. The canonical hook from Plan 10-02 has
// identical signature + behavior and will overwrite this file at merge time.
'use client';
import { useEffect, useState } from 'react';

export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    const mql = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReduced(mql.matches);
    const handler = (e: MediaQueryListEvent) => setReduced(e.matches);
    mql.addEventListener('change', handler);
    return () => mql.removeEventListener('change', handler);
  }, []);
  return reduced;
}
