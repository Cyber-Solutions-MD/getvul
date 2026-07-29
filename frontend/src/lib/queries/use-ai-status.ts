'use client';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

// D-23 gap closure (24-10): the real, non-admin-safe "is AI configured"
// signal -- the backend route this calls is require_viewer-gated, so this
// hook returns an accurate boolean for every role (Viewer/Analyst/Admin/
// Owner), unlike GET /api/v1/connectors (require_admin), which always 403s
// for Analyst/Viewer. Mirrors use-explain-cache.ts's exact single-GET
// useQuery shape -- an ordinary cheap GET, never the fetch()+ReadableStream
// SSE path.
export type AiStatusResult = { configured: boolean };

export function useAiStatus() {
  return useQuery({
    queryKey: queryKeys.ai.status(),
    queryFn: ({ signal }) => api<AiStatusResult>('/api/v1/ai/status', { signal }),
    staleTime: 60_000,
    retry: 1,
  });
}
