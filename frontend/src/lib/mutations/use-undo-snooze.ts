import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queries/keys';

type UndoSnoozeArgs = { id: string };

// D-H-08 reverse path. Backend semantics (per Plan 01 Task 3 recommendation):
// POST /vulnerabilities/{id}/unsnooze emits a `vuln.unsnooze` audit event and
// resets status to OPEN — symmetric to snooze for audit clarity. Same 3-key
// invalidation set as snooze because undo reverses snooze.
export function useUndoSnoozeMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id }: UndoSnoozeArgs) =>
      api<{ message: string }>(`/api/v1/vulnerabilities/${id}/unsnooze`, {
        method: 'POST',
        body: JSON.stringify({}),
        headers: { 'Content-Type': 'application/json' },
      }),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: queryKeys.vulnerabilities.stats() }),
        qc.invalidateQueries({ queryKey: queryKeys.vulnerabilities.dashboardTiles() }),
        qc.invalidateQueries({ queryKey: queryKeys.vulnerabilities.all }),
      ]);
    },
  });
}
