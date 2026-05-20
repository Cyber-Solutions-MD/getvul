// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

// Mock next/navigation BEFORE importing the hook.
const mockReplace = vi.fn();
let mockParams = new URLSearchParams();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mockReplace }),
  usePathname: () => '/dashboard',
  useSearchParams: () => ({
    get: (k: string) => mockParams.get(k),
    toString: () => mockParams.toString(),
  }),
}));

import { useUrlState } from './use-url-state';

const ranges = ['7d', '30d', '90d'] as const;

describe('useUrlState (D-D-04 — URL source-of-truth + Pitfall 7 XSS clamp)', () => {
  beforeEach(() => {
    mockReplace.mockReset();
    mockParams = new URLSearchParams();
  });

  it('returns the URL param value when it matches the allowed enum', () => {
    mockParams = new URLSearchParams('range=7d');
    const { result } = renderHook(() => useUrlState('range', ranges, '30d'));
    expect(result.current[0]).toBe('7d');
  });

  it('clamps unknown values to the default (mitigates T-10-10 reflected XSS)', () => {
    mockParams = new URLSearchParams('range=garbage');
    const { result } = renderHook(() => useUrlState('range', ranges, '30d'));
    expect(result.current[0]).toBe('30d');
  });

  it('never echoes raw <script>alert(1)</script> — falls back to default', () => {
    mockParams = new URLSearchParams('range=' + encodeURIComponent('<script>alert(1)</script>'));
    const { result } = renderHook(() => useUrlState('range', ranges, '30d'));
    expect(result.current[0]).toBe('30d');
    // Belt-and-braces: the returned value is one of the allow-listed strings only.
    expect((ranges as readonly string[]).includes(result.current[0])).toBe(true);
  });

  it('setValue replaces with the new param and scroll:false', () => {
    const { result } = renderHook(() => useUrlState('range', ranges, '30d'));
    act(() => result.current[1]('90d'));

    expect(mockReplace).toHaveBeenCalledTimes(1);
    expect(mockReplace.mock.calls[0][0]).toBe('/dashboard?range=90d');
    expect(mockReplace.mock.calls[0][1]).toEqual({ scroll: false });
  });

  it('setValue with default removes the param entirely (clean URL)', () => {
    mockParams = new URLSearchParams('range=7d');
    const { result } = renderHook(() => useUrlState('range', ranges, '30d'));
    act(() => result.current[1]('30d'));

    expect(mockReplace).toHaveBeenCalledTimes(1);
    expect(mockReplace.mock.calls[0][0]).toBe('/dashboard');
  });

  it('WR-04: null URL param does NOT cast to T even if allow-list contains empty string', () => {
    // Generic API: nothing stops a caller passing '' as an allowed value.
    // Previous shape cast `null` to T because `null ?? '' === ''` was in
    // the allow-list. Fixed shape short-circuits on `raw !== null`.
    const allowedWithEmpty = ['', 'on'] as const;
    mockParams = new URLSearchParams(); // no `key` at all
    const { result } = renderHook(() => useUrlState('flag', allowedWithEmpty, 'on'));
    expect(result.current[0]).toBe('on'); // falls back to default, not null
  });
});
