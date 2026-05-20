'use client';
import { useEffect, useState } from 'react';

// D-Ax-04 — listen for OS-level prefers-reduced-motion and let components
// conditionally drop animations. Cleanup removes the MQL listener so the hook
// doesn't leak on unmount.
export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const mql = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReduced(mql.matches);

    const handler = (e: MediaQueryListEvent) => setReduced(e.matches);
    mql.addEventListener('change', handler);
    return () => mql.removeEventListener('change', handler);
  }, []);

  return reduced;
}
