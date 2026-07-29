'use client';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';
import type { ExplainVulnResponse } from '@/lib/ai/use-explain-stream';

// use-vulnerability-detail.ts analog: the simplest existing single-GET
// useQuery shape in the codebase. Unlike use-explain-stream.ts, this one
// genuinely is a fast, non-streaming GET -- api() is the right tool here.
export type ExplainCacheResult = { cached: false } | ({ cached: true } & ExplainVulnResponse);

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
