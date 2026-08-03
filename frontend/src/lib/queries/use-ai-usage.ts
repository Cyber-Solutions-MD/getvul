'use client';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

// AIE-04 (28-04): mirrors use-ai-status.ts's exact single-GET useQuery shape
// -- an ordinary cheap admin-gated GET, never the fetch()+ReadableStream SSE
// path. The response shape is LOCKED by Plan 03 (backend/app/api/v1/ai/
// usage.py) -- field names here match that endpoint exactly, never invented.
//
// is_batch discriminates the two `prioritization` rows: null = no split
// (rows 1-4), false = on-demand (user_email != 'system:scheduler'), true =
// batch (user_email == 'system:scheduler'). NEVER a `status`-based split --
// a successful batch call also audits status="ok" (28-RESEARCH.md Pitfall 5).
export type AiUsageCapabilityRow = {
  resource_type: string;
  is_batch: boolean | null;
  calls: number;
  cost_usd: number;
  tokens: number;
};

export type AiUsageResult = {
  configured: boolean;
  model: string;
  monthly_budget_usd: number | null;
  spent_this_month_usd: number;
  breaker_tripped: boolean;
  capability_breakdown: AiUsageCapabilityRow[];
  degraded_calls_count: number;
};

export function useAiUsage() {
  return useQuery({
    queryKey: queryKeys.ai.usage(),
    queryFn: ({ signal }) => api<AiUsageResult>('/api/v1/ai/usage', { signal }),
    staleTime: 30_000,
    retry: 1,
  });
}
