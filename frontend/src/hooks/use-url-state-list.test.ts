// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

// Mock next/navigation BEFORE importing the hook. Extends the canonical
// use-url-state.test.ts mock with `getAll()` (multi-value) + `append()`.
const mockReplace = vi.fn();
let mockParams = new URLSearchParams();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mockReplace }),
  usePathname: () => '/dashboard/vulnerabilities',
  useSearchParams: () => ({
    get: (k: string) => mockParams.get(k),
    getAll: (k: string) => mockParams.getAll(k),
    toString: () => mockParams.toString(),
    append: (k: string, v: string) => mockParams.append(k, v),
  }),
}));

import { useUrlStateList } from './use-url-state-list';
import { useUrlState } from './use-url-state';

const severities = ['critical', 'high', 'medium', 'low'] as const;

describe('useUrlStateList (D-F-05 — multi-value URL state + XSS clamp / WR-04 carryover)', () => {
  beforeEach(() => {
    mockReplace.mockReset();
    mockParams = new URLSearchParams();
  });

  it('Test 1: getAll returns allow-listed values when URL has multiple ?severity=critical&severity=high', () => {
    mockParams = new URLSearchParams('severity=critical&severity=high');
    const { result } = renderHook(() => useUrlStateList('severity', severities));
    expect(result.current[0]).toEqual(['critical', 'high']);
  });

  it('Test 2: garbage URL values (<script>) are filtered out — only allow-listed values survive (XSS clamp)', () => {
    mockParams = new URLSearchParams(
      'severity=critical&severity=' + encodeURIComponent('<script>alert(1)</script>') + '&severity=high'
    );
    const { result } = renderHook(() => useUrlStateList('severity', severities));
    expect(result.current[0]).toEqual(['critical', 'high']);
    // Belt-and-braces: every element is allow-listed.
    for (const v of result.current[0]) {
      expect((severities as readonly string[]).includes(v)).toBe(true);
    }
  });

  it("Test 3: setValue(['critical','high']) appends two severity params + replace called with { scroll: false }", () => {
    const { result } = renderHook(() => useUrlStateList('severity', severities));
    act(() => result.current[1](['critical', 'high']));

    expect(mockReplace).toHaveBeenCalledTimes(1);
    const target = mockReplace.mock.calls[0][0] as string;
    expect(target.startsWith('/dashboard/vulnerabilities?')).toBe(true);
    expect(target).toContain('severity=critical');
    expect(target).toContain('severity=high');
    expect(mockReplace.mock.calls[0][1]).toEqual({ scroll: false });
  });

  it('Test 4: setValue([]) removes the key entirely (clean URL — no trailing empty param)', () => {
    mockParams = new URLSearchParams('severity=critical&severity=high&other=keep');
    const { result } = renderHook(() => useUrlStateList('severity', severities));
    act(() => result.current[1]([]));

    expect(mockReplace).toHaveBeenCalledTimes(1);
    const target = mockReplace.mock.calls[0][0] as string;
    expect(target).not.toContain('severity=');
    // Other params survive.
    expect(target).toContain('other=keep');
  });

  it("Test 5: toggle('critical') adds when absent, removes when present (idempotent in-out)", () => {
    // Start empty — toggle adds.
    mockParams = new URLSearchParams();
    const r1 = renderHook(() => useUrlStateList('severity', severities));
    act(() => r1.result.current[2]('critical'));
    let target = mockReplace.mock.calls[0][0] as string;
    expect(target).toContain('severity=critical');
    mockReplace.mockReset();

    // Already-present — toggle removes.
    mockParams = new URLSearchParams('severity=critical&severity=high');
    const r2 = renderHook(() => useUrlStateList('severity', severities));
    act(() => r2.result.current[2]('critical'));
    target = mockReplace.mock.calls[0][0] as string;
    expect(target).not.toContain('severity=critical');
    expect(target).toContain('severity=high');
  });

  it('Test 6: write-path also filters via allow-list (defense in depth)', () => {
    const { result } = renderHook(() => useUrlStateList('severity', severities));
    // Try to write a non-allow-listed value.
    act(() => result.current[1](['critical', 'evil' as never, 'high']));
    const target = mockReplace.mock.calls[0][0] as string;
    expect(target).toContain('severity=critical');
    expect(target).toContain('severity=high');
    expect(target).not.toContain('severity=evil');
  });

  it("Test 7: coexists with useUrlState('search', ...) on the same URL (different keys = no interference)", () => {
    // Set both kinds of params on URL.
    mockParams = new URLSearchParams('severity=critical&group=cve');
    const r = renderHook(() => {
      const list = useUrlStateList('severity', severities);
      const single = useUrlState('group', ['cve', 'host'] as const, 'cve');
      return { list, single };
    });
    expect(r.result.current.list[0]).toEqual(['critical']);
    expect(r.result.current.single[0]).toBe('cve');
  });
});
