'use client';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';
import type { ExplainVulnResponse } from '@/lib/ai/use-explain-stream';

// use-vulnerability-detail.ts analog: the simplest existing single-GET
// useQuery shape in the codebase. Unlike use-explain-stream.ts, this one
// genuinely is a fast, non-streaming GET -- api() is the right tool here.
// Phase 25 (D-01): the /explain-remediation-guidance GET route additively
// returns `groundable` on a cache miss (the D-01 deterministic pre-
// generation-gate pre-signal, so the client can render the
// insufficient-evidence card before any click) -- every OTHER existing GET
// route still returns exactly `{ cached: false }` with no `groundable` key,
// so this field stays optional and the component must check `=== false`
// explicitly, never treat a missing field as falsy-refusal.
// Phase 26 (D-02): the /explain-prioritization GET route additively returns
// `queued` on a cache miss once Plan 06's AiBatchJob registry exists (this
// plan's own GET route still returns the baseline {cached:false} with no
// queued key -- the field rides along unchanged the moment Plan 06 starts
// populating it). Optional + checked `=== true` explicitly for the same
// reason `groundable` is checked `=== false` explicitly: every other
// resourceType's GET route never returns `queued` at all.
export type ExplainCacheResult =
  | { cached: false; groundable?: boolean; queued?: boolean }
  | ({ cached: true } & ExplainVulnResponse);

/**
 * useExplainCache(resourceType, resourceId) -- the cheap cache-check (D-09):
 * a single GET, never a model call. A hit renders the validated explanation
 * immediately; a miss lets the section decide the state-appropriate
 * affordance. `resourceType` is always interpolated (D-15) -- never a fixed
 * resource-kind literal.
 */
export function useExplainCache(resourceType: string, resourceId: string) {
  return useQuery({
    queryKey: queryKeys.ai.explain(resourceType, resourceId),
    queryFn: ({ signal }) =>
      api<ExplainCacheResult>(`/api/v1/ai/explain-${resourceType}/${resourceId}`, { signal }),
    staleTime: 30_000,
    retry: 1,
  });
}
