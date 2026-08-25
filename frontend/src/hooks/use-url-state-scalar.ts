'use client';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useCallback } from 'react';

// D-17 / RESEARCH State-of-the-Art gap: useUrlState (use-url-state.ts) and
// useUrlStateList (use-url-state-list.ts) are string-enum-clamped ONLY —
// `allowed.includes(raw)`. Neither can express a boolean (cisa_kev,
// exploit_available, sla_breached, asset_internet_facing, internet_facing)
// or a bounded numeric range (age_days_min). This file is the scalar-value
// sibling pair that fills that gap, mirroring the same XSS-clamp discipline
// (T-44-11): the URL is user-controllable, so a value that doesn't parse to
// exactly the expected shape falls back to `defaultValue` — it never reaches
// the render tree unvalidated.

// Boolean round-trip: the ONLY two valid on-wire values are the literal
// strings 'true'/'false'. Anything else (missing param, malformed value, an
// injected string) falls back to `defaultValue`.
export function useUrlStateBool(
  key: string,
  defaultValue: boolean
): [boolean, (next: boolean) => void] {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  const raw = params?.get(key) ?? null;
  const value: boolean = raw === 'true' ? true : raw === 'false' ? false : defaultValue;

  const setValue = useCallback(
    (next: boolean) => {
      const sp = new URLSearchParams(params?.toString() ?? '');
      if (next === defaultValue) sp.delete(key);
      else sp.set(key, next ? 'true' : 'false');
      const qs = sp.toString();
      const target = qs ? `${pathname}?${qs}` : (pathname ?? '/');
      router.replace(target, { scroll: false });
    },
    [router, pathname, params, key, defaultValue]
  );

  return [value, setValue];
}

export type UrlStateNumberOptions = {
  min?: number;
  max?: number;
  defaultValue: number | null;
};

// Bounded-integer round-trip: `Number(raw)` is rejected (falls back to
// `defaultValue`) unless it is finite, an integer, and within [min, max] —
// no unparsed string ever reaches a caller, and no float/NaN/Infinity can
// smuggle through as a "numeric" value.
export function useUrlStateNumber(
  key: string,
  opts: UrlStateNumberOptions
): [number | null, (next: number | null) => void] {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const { min, max, defaultValue } = opts;

  const raw = params?.get(key) ?? null;
  const parsed = raw !== null && raw !== '' ? Number(raw) : NaN;
  const inRange =
    Number.isFinite(parsed) &&
    Number.isInteger(parsed) &&
    (min === undefined || parsed >= min) &&
    (max === undefined || parsed <= max);
  const value: number | null = inRange ? parsed : defaultValue;

  const setValue = useCallback(
    (next: number | null) => {
      const sp = new URLSearchParams(params?.toString() ?? '');
      if (next === null || next === defaultValue) sp.delete(key);
      else sp.set(key, String(next));
      const qs = sp.toString();
      const target = qs ? `${pathname}?${qs}` : (pathname ?? '/');
      router.replace(target, { scroll: false });
    },
    [router, pathname, params, key, defaultValue]
  );

  return [value, setValue];
}
