'use client';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useCallback } from 'react';

// D-D-04, D-D-05 — URL is the source-of-truth for filter state (deep-linkable).
// Pitfall 7 / T-10-10: the URL is user-controllable. We MUST clamp `raw` to
// the `allowed` enum BEFORE returning, so reflected-XSS-via-?range= can't
// land arbitrary strings in the render tree (e.g., raw HTML/script in a
// shareable link). The default value falls through when the URL is missing
// or has a value outside the allow-list.
export function useUrlState<T extends string>(
  key: string,
  allowed: readonly T[],
  defaultValue: T
): [T, (next: T) => void] {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  const raw = params?.get(key) ?? null;
  // WR-04: previous shape was `allowed.includes(raw ?? '')` — if `allowed`
  // ever contains '' (the generic API allows it), a missing URL param would
  // produce `raw=null`, the includes check would pass on '', and `(raw as T)`
  // would cast `null` to T. Tighten so null short-circuits the cast.
  const value: T =
    raw !== null && (allowed as readonly string[]).includes(raw)
      ? (raw as T)
      : defaultValue;

  const setValue = useCallback(
    (next: T) => {
      const sp = new URLSearchParams(params?.toString() ?? '');
      if (next === defaultValue) sp.delete(key);
      else sp.set(key, next);
      const qs = sp.toString();
      const target = qs ? `${pathname}?${qs}` : (pathname ?? '/');
      router.replace(target, { scroll: false });
    },
    [router, pathname, params, key, defaultValue]
  );

  return [value, setValue];
}
