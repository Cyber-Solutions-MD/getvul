'use client';
import { useSyncExternalStore, useMemo, useRef } from 'react';
import { useQueryClient, type QueryKey } from '@tanstack/react-query';

// D-S-03 — QueryCache subscription bridge. TanStack v5 has no first-party
// "watch errors across a set of keys" hook; we compose one via
// useSyncExternalStore + QueryCache.subscribe + QueryCache.findAll.
//
// Consumed by <PartialFailureBanner /> in default-mode (banner aggregates
// failures across all configured watchKeys). Override-mode bypasses this
// hook entirely and accepts an explicit `errors` prop.

export type QueryError = {
  queryKey: QueryKey;
  error: Error;
  code: number | string;
  requestId: string;
};

function extractCode(err: Error): number | string {
  // Phase 10 microcopy.ts pattern: error objects carry .code when api.ts
  // attaches it; fall back to 'unknown' so the banner still renders.
  return (err as unknown as { code?: number | string }).code ?? 'unknown';
}

function extractRequestId(err: Error): string {
  return (err as unknown as { requestId?: string }).requestId ?? 'unknown';
}

/**
 * Watch a set of query keys for error state. Re-renders the consuming
 * component when any matching query transitions success ↔ error.
 *
 * @param keys — array of partial query keys (e.g. `[['vulnerabilities'], ['connectors']]`).
 *               Uses `queryCache.findAll({ queryKey })` partial-match semantics.
 */
export function useQueryErrors(keys: readonly QueryKey[]): QueryError[] {
  const qc = useQueryClient();
  const cache = qc.getQueryCache();

  // Cache the fingerprint+value tuple in a ref so identical snapshots return
  // the same array reference (Pitfall 4 — useSyncExternalStore re-renders on
  // any reference change of the snapshot).
  const cacheRef = useRef<{ fingerprint: string; value: QueryError[] } | null>(null);

  const subscribe = useMemo(
    () => (cb: () => void) => cache.subscribe(cb),
    [cache]
  );

  const getSnapshot = useMemo(
    () => () => {
      const errors: QueryError[] = [];
      for (const key of keys) {
        for (const q of cache.findAll({ queryKey: key })) {
          if (q.state.status === 'error' && q.state.error) {
            const err = q.state.error as Error;
            errors.push({
              queryKey: q.queryKey,
              error: err,
              code: extractCode(err),
              requestId: extractRequestId(err),
            });
          }
        }
      }
      // Fingerprint snapshot so identical error sets return the same array
      // reference — prevents render churn when cache fires events that don't
      // change the watched-error set.
      const fingerprint = errors
        .map(
          (e) => `${JSON.stringify(e.queryKey)}|${e.code}|${e.requestId}`
        )
        .join(',');
      const prev = cacheRef.current;
      if (prev && prev.fingerprint === fingerprint) {
        return prev.value;
      }
      cacheRef.current = { fingerprint, value: errors };
      return errors;
    },
    [cache, keys]
  );

  // SSR fallback: no errors during server render.
  const getServerSnapshot = () => [] as QueryError[];

  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
