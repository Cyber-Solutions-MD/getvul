// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

// Mock next/navigation BEFORE importing the hook.
// Extends the canonical mock in use-url-state.test.ts with `getAll` + `append`
// so the multi-value `?severity=critical&severity=high` shape is exercised.
const mockReplace = vi.fn();
let mockParams = new URLSearchParams();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mockReplace }),
  usePathname: () => '/dashboard/vulnerabilities',
  useSearchParams: () => ({
    get: (k: string) => mockParams.get(k),
    getAll: (k: string) => mockParams.getAll(k),
    toString: () => mockParams.toString(),
  }),
}));

// Wave 1 (Plan 11-03) will create this file. Import here is the RED signal.
import { useUrlStateList } from './use-url-state-list';

const severities = ['critical', 'high', 'medium', 'low'] as const;

describe('useUrlStateList (D-F-05 — multi-value URL state + XSS clamp)', () => {
  beforeEach(() => {
    mockReplace.mockReset();
    mockParams = new URLSearchParams();
  });

  it('returns allow-listed values when URL has multiple ?severity=critical&severity=high', () => {
    mockParams = new URLSearchParams('severity=critical&severity=high');
    const { result } = renderHook(() => useUrlStateList('severity', severities));
    const [value] = result.current;
    expect(value).toEqual(['critical', 'high']);
  });

  it('filters out garbage URL values to mitigate reflected XSS (T-10-10 carryover)', () => {
    // garbage URL values (XSS payload + unknown enum) must be filtered out
    mockParams = new URLSearchParams(
      'severity=' +
        encodeURIComponent('<script>alert(1)</script>') +
        '&severity=high&severity=evil'
    );
    const { result } = renderHook(() => useUrlStateList('severity', severities));
    const [value] = result.current;
    // Only 'high' survives the allow-list clamp
    expect(value).toEqual(['high']);
    // Belt-and-braces: every returned element is in the allow-list
    for (const v of value) {
      expect((severities as readonly string[]).includes(v)).toBe(true);
    }
  });

  it("setValue(['critical','high']) appends two severity params with scroll:false", () => {
    const { result } = renderHook(() => useUrlStateList('severity', severities));
    const [, setValue] = result.current;
    act(() => setValue(['critical', 'high']));

    expect(mockReplace).toHaveBeenCalledTimes(1);
    const [target, opts] = mockReplace.mock.calls[0];
    expect(target).toContain('severity=critical');
    expect(target).toContain('severity=high');
    expect(opts).toEqual({ scroll: false });
  });

  it('setValue([]) removes the key entirely (clean URL — no trailing ?severity=)', () => {
    mockParams = new URLSearchParams('severity=critical&severity=high');
    const { result } = renderHook(() => useUrlStateList('severity', severities));
    const [, setValue] = result.current;
    act(() => setValue([]));

    expect(mockReplace).toHaveBeenCalledTimes(1);
    const [target] = mockReplace.mock.calls[0];
    expect(target).not.toContain('severity=');
    expect(target).not.toMatch(/severity(?:=|&|$)/);
  });

  it("toggle('critical') adds when absent, removes when present (idempotent in-out)", () => {
    const { result, rerender } = renderHook(() =>
      useUrlStateList('severity', severities)
    );
    const [, , toggle] = result.current;

    // Add when absent
    act(() => toggle('critical'));
    expect(mockReplace).toHaveBeenCalledTimes(1);
    expect(mockReplace.mock.calls[0][0]).toContain('severity=critical');

    // Simulate URL update to reflect the new state and rerender
    mockParams = new URLSearchParams('severity=critical');
    rerender();

    // Toggle again → remove
    act(() => result.current[2]('critical'));
    expect(mockReplace).toHaveBeenCalledTimes(2);
    const [target] = mockReplace.mock.calls[1];
    expect(target).not.toContain('severity=critical');
  });

  it('write-path also filters via allow-list (defense in depth — XSS clamp on setValue)', () => {
    const { result } = renderHook(() => useUrlStateList('severity', severities));
    const [, setValue] = result.current;
    // calling setValue with an unknown value produces no URL update for that value
    act(() => setValue(['evil' as never, 'critical']));

    expect(mockReplace).toHaveBeenCalledTimes(1);
    const [target] = mockReplace.mock.calls[0];
    expect(target).toContain('severity=critical');
    expect(target).not.toContain('severity=evil');
  });

  it('coexists with single-value useUrlState (different keys do not interfere)', () => {
    mockParams = new URLSearchParams('severity=critical&search=log4j');
    const { result } = renderHook(() => useUrlStateList('severity', severities));
    const [value] = result.current;
    expect(value).toEqual(['critical']);
    // The other key (`search`) survives on the underlying params
    expect(mockParams.get('search')).toBe('log4j');
  });
});
