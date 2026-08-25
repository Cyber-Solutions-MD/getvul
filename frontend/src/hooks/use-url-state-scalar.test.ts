// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

// Mock next/navigation BEFORE importing the hooks — mirrors use-url-state.test.ts.
const mockReplace = vi.fn();
let mockParams = new URLSearchParams();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mockReplace }),
  usePathname: () => '/dashboard/vulnerabilities',
  useSearchParams: () => ({
    get: (k: string) => mockParams.get(k),
    toString: () => mockParams.toString(),
  }),
}));

import { useUrlStateBool, useUrlStateNumber } from './use-url-state-scalar';

describe('useUrlStateBool (D-17 — boolean URL-state clamp, T-44-11)', () => {
  beforeEach(() => {
    mockReplace.mockReset();
    mockParams = new URLSearchParams();
  });

  it('reads "true" as true', () => {
    mockParams = new URLSearchParams('cisa_kev=true');
    const { result } = renderHook(() => useUrlStateBool('cisa_kev', false));
    expect(result.current[0]).toBe(true);
  });

  it('reads "false" as false', () => {
    mockParams = new URLSearchParams('cisa_kev=false');
    const { result } = renderHook(() => useUrlStateBool('cisa_kev', true));
    expect(result.current[0]).toBe(false);
  });

  it('clamps any non "true"/"false" value to the default (reflected-XSS defense)', () => {
    mockParams = new URLSearchParams(
      'cisa_kev=' + encodeURIComponent('<script>alert(1)</script>')
    );
    const { result } = renderHook(() => useUrlStateBool('cisa_kev', false));
    expect(result.current[0]).toBe(false);
  });

  it('missing param falls back to the default', () => {
    const { result } = renderHook(() => useUrlStateBool('cisa_kev', false));
    expect(result.current[0]).toBe(false);
  });

  it('setValue(true) writes the literal string "true"', () => {
    const { result } = renderHook(() => useUrlStateBool('cisa_kev', false));
    act(() => result.current[1](true));
    expect(mockReplace).toHaveBeenCalledTimes(1);
    expect(mockReplace.mock.calls[0][0]).toBe('/dashboard/vulnerabilities?cisa_kev=true');
    expect(mockReplace.mock.calls[0][1]).toEqual({ scroll: false });
  });

  it('setValue(default) removes the param entirely (clean URL)', () => {
    mockParams = new URLSearchParams('cisa_kev=true');
    const { result } = renderHook(() => useUrlStateBool('cisa_kev', false));
    act(() => result.current[1](false));
    expect(mockReplace.mock.calls[0][0]).toBe('/dashboard/vulnerabilities');
  });
});

describe('useUrlStateNumber (D-17 — bounded-numeric URL-state clamp, T-44-11)', () => {
  beforeEach(() => {
    mockReplace.mockReset();
    mockParams = new URLSearchParams();
  });

  it('reads a well-formed integer within bounds', () => {
    mockParams = new URLSearchParams('age_days_min=30');
    const { result } = renderHook(() =>
      useUrlStateNumber('age_days_min', { min: 0, defaultValue: null })
    );
    expect(result.current[0]).toBe(30);
  });

  it('rejects a non-numeric value, falling back to the default', () => {
    mockParams = new URLSearchParams(
      'age_days_min=' + encodeURIComponent('<script>alert(1)</script>')
    );
    const { result } = renderHook(() =>
      useUrlStateNumber('age_days_min', { min: 0, defaultValue: null })
    );
    expect(result.current[0]).toBeNull();
  });

  it('rejects a value below the configured min', () => {
    mockParams = new URLSearchParams('age_days_min=-5');
    const { result } = renderHook(() =>
      useUrlStateNumber('age_days_min', { min: 0, defaultValue: null })
    );
    expect(result.current[0]).toBeNull();
  });

  it('rejects a non-integer (float) value', () => {
    mockParams = new URLSearchParams('age_days_min=30.5');
    const { result } = renderHook(() =>
      useUrlStateNumber('age_days_min', { min: 0, defaultValue: null })
    );
    expect(result.current[0]).toBeNull();
  });

  it('missing param falls back to the default', () => {
    const { result } = renderHook(() =>
      useUrlStateNumber('age_days_min', { min: 0, defaultValue: null })
    );
    expect(result.current[0]).toBeNull();
  });

  it('setValue(30) writes the numeric string', () => {
    const { result } = renderHook(() =>
      useUrlStateNumber('age_days_min', { min: 0, defaultValue: null })
    );
    act(() => result.current[1](30));
    expect(mockReplace.mock.calls[0][0]).toBe('/dashboard/vulnerabilities?age_days_min=30');
  });

  it('setValue(null) removes the param entirely', () => {
    mockParams = new URLSearchParams('age_days_min=30');
    const { result } = renderHook(() =>
      useUrlStateNumber('age_days_min', { min: 0, defaultValue: null })
    );
    act(() => result.current[1](null));
    expect(mockReplace.mock.calls[0][0]).toBe('/dashboard/vulnerabilities');
  });
});
