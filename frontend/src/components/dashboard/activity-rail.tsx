'use client';
import { ActivityFeed } from '@/components/ui/activity-feed';
import { PartialFailureBanner } from '@/components/states';
import { useRecentNotifications } from '@/lib/queries/use-recent-notifications';
import { microcopy } from './microcopy';

// Phase 11 D-S-06 retrofit: error → <PartialFailureBanner>.
// Loading state stays inline because the shape isn't table-shaped — see
// 11-RESEARCH.md §Phase 10 Retrofit Audit (planner discretion preserved).
// D-A-06..07 + D-M-01: right-rail behavior — sticky at ≥1280px, collapses to
// a full-width section with a visible h2 below the main column at <1280px.
// At ≥1280px the <aside aria-label> is the accessible name and the h2 is
// visually hidden (sr-only) to avoid double labeling.

export function ActivityRail() {
  const q = useRecentNotifications();

  return (
    <aside
      aria-label={microcopy.activity.h2}
      className="rounded-lg border border-border-subtle bg-surface p-5 xl:sticky xl:top-4 xl:h-fit"
    >
      <h2 className="mb-3 text-lg font-semibold text-text xl:sr-only">
        {microcopy.activity.h2}
      </h2>

      {q.isPending && (
        <div aria-busy="true" className="space-y-3">
          {[0, 1, 2, 3, 4].map((i) => (
            <div key={i} className="h-10 rounded-md bg-surface-2 animate-pulse" />
          ))}
        </div>
      )}

      {q.error && (
        <PartialFailureBanner
          errors={[
            {
              code: (q.error as { code?: number | string } | null)?.code ?? 'unknown',
              requestId: (q.error as { requestId?: string } | null)?.requestId ?? 'unknown',
              message: undefined,
            },
          ]}
          onRetry={() => q.refetch()}
          source="Activity"
        />
      )}

      {q.data && (
        <ActivityFeed items={q.data.items} emptyCopy={microcopy.activity.empty} />
      )}
    </aside>
  );
}
