import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queries/keys';

type SnoozeArgs = { id: string; until?: string };

export function useSnoozeMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, until }: SnoozeArgs) =>
      api<{ message: string; until: string }>(
        `/api/v1/vulnerabilities/${id}/snooze`,
        {
          method: 'POST',
          body: JSON.stringify({ until }),
          headers: { 'Content-Type': 'application/json' },
        }
      ),
    onSuccess: async () => {
      // D-D-13 verbatim: invalidate three keys after a successful snooze.
      // 1) stats — top_vuln / critical_open / sla_at_risk may shift
      // 2) dashboard-tiles — same root surface
      // 3) all (vulnerability list / detail) — row changes status
      await Promise.all([
        qc.invalidateQueries({ queryKey: queryKeys.vulnerabilities.stats() }),
        qc.invalidateQueries({ queryKey: queryKeys.vulnerabilities.dashboardTiles() }),
        qc.invalidateQueries({ queryKey: queryKeys.vulnerabilities.all }),
      ]);
    },
  });
}
