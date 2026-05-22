'use client';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useMemo } from 'react';

// D-F-05 + Phase 10 WR-04 carryover. allowed.includes(value) is the XSS clamp —
// values reflected from URL never reach the render tree without allow-list
// validation. The clamp runs BOTH on READ (so reflected `<script>` in a
// shareable link never lands as a chip label) AND on WRITE (defense in depth
// against any caller that bypasses the chip-bar UI and calls setValue
// directly with an un-validated value).
//
// Multi-value sibling to useUrlState. Used by the vuln-page chip-bar to keep
// severity / source / status filters in the URL (`?severity=critical&severity=high`).
export function useUrlStateList<T extends string>(
  key: string,
  allowed: readonly T[],
  defaultValue: readonly T[] = []
): [readonly T[], (next: readonly T[]) => void, (item: T) => void] {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  // getAll() reads multi-value; Next 15 ReadonlyURLSearchParams supports it.
  const raw = useMemo(() => params?.getAll(key) ?? [], [params, key]);

  // XSS clamp on READ (mirrors WR-04 from useUrlState): keep only allow-listed values.
  const value: readonly T[] = useMemo(
    () => raw.filter((v): v is T => (allowed as readonly string[]).includes(v)),
    [raw, allowed]
  );

  const setValue = useCallback(
    (next: readonly T[]) => {
      const sp = new URLSearchParams(params?.toString() ?? '');
      sp.delete(key);
      // XSS clamp on WRITE (defense in depth): drop anything not in the allow-list.
      next
        .filter((v) => (allowed as readonly string[]).includes(v))
        .forEach((v) => sp.append(key, v));
      const qs = sp.toString();
      const target = qs ? `${pathname}?${qs}` : (pathname ?? '/');
      router.replace(target, { scroll: false });
    },
    [router, pathname, params, key, allowed]
  );

  // Convenience: toggle one item in/out. Adds when absent, removes when present.
  const toggle = useCallback(
    (item: T) =>
      setValue(
        value.includes(item) ? value.filter((v) => v !== item) : [...value, item]
      ),
    [value, setValue]
  );

  return [value.length ? value : defaultValue, setValue, toggle];
}
