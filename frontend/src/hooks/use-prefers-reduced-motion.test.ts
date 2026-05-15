// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { usePrefersReducedMotion } from './use-prefers-reduced-motion';

// Build a controllable MediaQueryList stub.
function createMatchMedia(initialMatches: boolean) {
  const listeners = new Set<(e: MediaQueryListEvent) => void>();
  const mql = {
    matches: initialMatches,
    media: '(prefers-reduced-motion: reduce)',
    addEventListener: (_type: string, cb: (e: MediaQueryListEvent) => void) => {
      listeners.add(cb);
    },
    removeEventListener: (_type: string, cb: (e: MediaQueryListEvent) => void) => {
      listeners.delete(cb);
    },
    dispatchChange: (matches: boolean) => {
      mql.matches = matches;
      for (const cb of listeners) cb({ matches } as MediaQueryListEvent);
    },
    listenerCount: () => listeners.size,
  };
  return mql;
}

describe('usePrefersReducedMotion (D-Ax-04)', () => {
  let mql: ReturnType<typeof createMatchMedia>;

  beforeEach(() => {
    mql = createMatchMedia(false);
    vi.stubGlobal('matchMedia', vi.fn(() => mql));
  });

  it('returns initial matches value', () => {
    mql = createMatchMedia(true);
    vi.stubGlobal('matchMedia', vi.fn(() => mql));
    const { result } = renderHook(() => usePrefersReducedMotion());
    expect(result.current).toBe(true);
  });

  it('flips to true on change event with matches:true', () => {
    const { result } = renderHook(() => usePrefersReducedMotion());
    expect(result.current).toBe(false);

    act(() => mql.dispatchChange(true));
    expect(result.current).toBe(true);
  });

  it('removes listener on unmount (no leak)', () => {
    const { unmount } = renderHook(() => usePrefersReducedMotion());
    expect(mql.listenerCount()).toBe(1);
    unmount();
    expect(mql.listenerCount()).toBe(0);
  });
});
