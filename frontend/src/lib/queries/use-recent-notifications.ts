import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

export type ActivityCategory =
  | 'new_critical_vuln'
  | 'sla_breach'
  | 'sync_failure'
  | 'risk_change';

export type ActivityItem = {
  id: string;
  category: ActivityCategory;
  title: string;
  body: string | null;
  occurred_at: string; // ISO timestamp
  href?: string;
};

export type RecentNotificationsResponse = {
  items: ActivityItem[];
  total: number;
};

export function useRecentNotifications() {
  return useQuery({
    queryKey: queryKeys.notifications.recent(5),
    queryFn: ({ signal }) =>
      api<RecentNotificationsResponse>(
        '/api/v1/notifications?page=1&page_size=5',
        { signal }
      ),
    staleTime: 30_000, // D-D-06: 30s for notifications (more volatile than stats)
    retry: 0, // not in retry tier
  });
}
