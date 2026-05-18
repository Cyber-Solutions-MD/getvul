import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

// BL-02: TriageRow's `host`/`cvss_v3_score`/`sla_due_at` do NOT exist on the
// backend `VulnerabilitySummary` (the schema used by the list endpoint). The
// backend exposes `asset_hostname` for the host, and does not include CVSS or
// SLA in the lightweight list payload at all — only on the detail view.
//
// Per phase guidance ("don't change the backend contract — Phase 11+ depends
// on it"), we adapt the response in `select` and surface CVSS / SLA as `null`
// so the Top5Card's existing render-time fallbacks ('—' for CVSS, gray pill
// for SLA) kick in. `host` is wired to `asset_hostname`. The contract drift
// shows up at runtime today (real backend → empty hosts, CVSS column = '—',
// SLA pill stuck on null branch); this aligns the adapter so the rendered
// view matches reality.
export type TriageRow = {
  id: string;
  cve_id: string | null;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  host: string | null;
  cvss_v3_score: number | null;
  cisa_kev: boolean;
  sla_due_at: string | null;
};

export type TopTriageResponse = {
  items: TriageRow[];
  total: number;
};

// Backend payload — keep in sync with `backend/app/vulnerabilities/schemas.py`
// `VulnerabilitySummary`. The list endpoint returns `PaginatedResponse[VulnerabilitySummary]`.
type BackendSummary = {
  id: string;
  cve_id: string | null;
  severity: string;
  source: string;
  status: string;
  exploit_available: boolean;
  cisa_kev: boolean;
  affected_product: string | null;
  asset_id: string | null;
  asset_hostname: string | null;
  first_detected_at: string;
  last_seen_at: string;
  // Optional fields the backend MAY expose on the summary in future phases.
  // Treated as nullable for forward compatibility — adapter accepts them if
  // present, falls back to null otherwise.
  cvss_v3_score?: number | string | null;
  sla_due_at?: string | null;
};

type BackendResponse = {
  items: BackendSummary[];
  total: number;
};

const ALLOWED_SEVERITIES = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] as const;
type AllowedSeverity = (typeof ALLOWED_SEVERITIES)[number];

function adaptSeverity(raw: string): AllowedSeverity {
  return (ALLOWED_SEVERITIES as readonly string[]).includes(raw)
    ? (raw as AllowedSeverity)
    : 'LOW';
}

function adapt(payload: BackendResponse): TopTriageResponse {
  return {
    total: payload.total,
    items: (payload.items ?? []).map((r) => ({
      id: r.id,
      cve_id: r.cve_id,
      severity: adaptSeverity(r.severity),
      host: r.asset_hostname ?? null,
      cvss_v3_score:
        r.cvss_v3_score !== undefined && r.cvss_v3_score !== null
          ? Number(r.cvss_v3_score)
          : null,
      cisa_kev: r.cisa_kev,
      sla_due_at: r.sla_due_at ?? null,
    })),
  };
}

export function useTopTriage(limit = 5) {
  return useQuery({
    queryKey: queryKeys.vulnerabilities.topTriage(limit),
    queryFn: ({ signal }) =>
      api<BackendResponse>(`/api/v1/vulnerabilities?sort=triage&limit=${limit}`, {
        signal,
      }),
    select: adapt,
    staleTime: 60_000,
    retry: 0, // D-D-07: only stats + dashboard-tiles tier retries
  });
}
