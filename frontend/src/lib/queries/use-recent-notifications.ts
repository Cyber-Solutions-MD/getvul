import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

// Allowed categories Plan 10 maps to ActivityFeed icon/variant. Anything outside
// this list (the backend has a longer enum) is collapsed to `sync_failure` —
// the existing icon/variant pair is the safest neutral fallback.
export type ActivityCategory =
  | 'new_critical_vuln'
  | 'sla_breach'
  | 'sync_failure'
  | 'risk_change';

const ALLOWED_CATEGORIES: ReadonlyArray<ActivityCategory> = [
  'new_critical_vuln',
  'sla_breach',
  'sync_failure',
  'risk_change',
];

export type ActivityItem = {
  id: string;
  category: ActivityCategory;
  title: string;
  body: string | null;
  occurred_at: string;
  href?: string;
};

export type RecentNotificationsResponse = {
  items: ActivityItem[];
  total: number;
};

// Backend payload shape from /api/v1/notifications. Keys differ from
// ActivityItem (created_at vs occurred_at, message vs body); we adapt inside
// the hook via `select` so callers see one canonical shape.
type BackendNotification = {
  id: string;
  title: string;
  message: string | null;
  category: string;
  created_at: string;
  resource_type?: string | null;
  resource_id?: string | null;
};

type BackendResponse = {
  items: BackendNotification[];
  total: number;
};

function adaptCategory(raw: string): ActivityCategory {
  return (ALLOWED_CATEGORIES as readonly string[]).includes(raw)
    ? (raw as ActivityCategory)
    : 'sync_failure';
}

function adapt(payload: BackendResponse): RecentNotificationsResponse {
  return {
    total: payload.total,
    items: (payload.items ?? []).map((n) => ({
      id: n.id,
      category: adaptCategory(n.category),
      title: n.title,
      body: n.message ?? null,
      occurred_at: n.created_at,
    })),
  };
}

export function useRecentNotifications() {
  return useQuery({
    queryKey: queryKeys.notifications.recent(5),
    queryFn: ({ signal }) =>
      api<BackendResponse>('/api/v1/notifications?page=1&page_size=5', { signal }),
    select: adapt,
    staleTime: 30_000, // D-D-06: 30s for notifications (more volatile than stats)
    retry: 0,
  });
}
