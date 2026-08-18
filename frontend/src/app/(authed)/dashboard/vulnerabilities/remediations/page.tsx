'use client';
/**
 * /dashboard/vulnerabilities/remediations — CAMP-01 entry point.
 *
 * Brand-new page (38-RESEARCH.md Pitfall 8 — GET /remediations/grouped had
 * zero prior frontend consumers before this plan). Composition mirrors
 * tickets/page.tsx:
 *   ErrorBoundary > Suspense > RemediationsPageInner
 *
 * State branches (mutually exclusive, WR-13):
 *   q.error → PartialFailureBanner
 *   isLoading → SkeletonTable
 *   items.length === 0 → EmptyState ("No remediation groups yet")
 *   else → RemediationsTable + Pagination
 *
 * "Start campaign" → useStartCampaign() POSTs /api/v1/campaigns and routes
 * to /dashboard/campaigns/{id} in both the newly-created AND the D-11
 * already-existed case (toast copy differs — see use-campaign-mutations.ts).
 */
import { Suspense, useCallback, useState, type ReactNode } from 'react';
import { SkeletonTable, EmptyState, PartialFailureBanner, type SkeletonColumn } from '@/components/states';
import Pagination from '@/components/ui/Pagination';
import { ErrorBoundary } from '@/components/ui/error-boundary';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { RemediationsTable } from '@/components/campaigns/remediations-table';
import { useRemediationsGrouped } from '@/lib/queries/use-remediations-grouped';
import { useStartCampaign } from '@/lib/queries/use-campaign-mutations';

const SKELETON_COLUMNS: SkeletonColumn[] = [
  { kind: 'text', width: 260 }, // remediation
  { kind: 'mono', width: 40 }, // hosts
  { kind: 'mono', width: 70 }, // members
  { kind: 'text', width: 20 }, // severity
  { kind: 'badge', width: 110 }, // Start campaign CTA
];

function pageErrorFallback(err: Error, reset: () => void): ReactNode {
  return (
    <div className="space-y-4 p-6">
      <h1 className="sr-only">Remediations</h1>
      <PartialFailureBanner
        errors={[{ code: 'crash', requestId: err.message || 'unknown' }]}
        onRetry={reset}
      />
    </div>
  );
}

function RemediationsPageInner() {
  useDocumentTitle('Remediations');
  const [page, setPage] = useState(1);

  const q = useRemediationsGrouped(page);
  const startCampaign = useStartCampaign();

  const onStartCampaign = useCallback(
    (remediationId: string) => {
      startCampaign.mutate(remediationId);
    },
    [startCampaign],
  );

  const isLoading = q.isPending;
  const items = q.data?.items ?? [];
  const totalPages = q.data?.total_pages ?? 1;

  return (
    <div className="space-y-4 p-6">
      <header className="space-y-1">
        <div className="text-xs uppercase tracking-wide text-text-muted">
          Remediations · {q.data?.total ?? 0} {q.data?.total === 1 ? 'group' : 'groups'}
        </div>
        <h1 className="text-2xl font-semibold text-text">Remediations</h1>
      </header>

      {/* WR-13: state branches are mutually exclusive — error > loading > empty > data. */}
      {q.error ? (
        <PartialFailureBanner
          errors={[
            {
              code: 'http_error',
              requestId: String((q.error as Error).message) || 'unknown',
            },
          ]}
          onRetry={() => q.refetch()}
        />
      ) : isLoading ? (
        <SkeletonTable columns={SKELETON_COLUMNS} rows={10} />
      ) : items.length === 0 ? (
        <EmptyState>
          <EmptyState.Title>No remediation groups yet</EmptyState.Title>
          <EmptyState.Body>
            Findings that share a fix will show up here, grouped, once
            scanners report them. Start a campaign on a group to bulk-create
            tickets instead of ticketing hosts one at a time.
          </EmptyState.Body>
        </EmptyState>
      ) : (
        <>
          <RemediationsTable
            rows={items}
            onStartCampaign={onStartCampaign}
            isStarting={startCampaign.isPending}
          />
          {totalPages > 1 && (
            <Pagination
              page={page}
              totalPages={totalPages}
              total={q.data?.total ?? 0}
              pageSize={q.data?.page_size ?? 25}
              onPageChange={setPage}
            />
          )}
        </>
      )}
    </div>
  );
}

const PAGE_FALLBACK = (
  <div className="space-y-4 p-6">
    <h1 className="sr-only">Remediations</h1>
    <SkeletonTable columns={SKELETON_COLUMNS} rows={10} />
  </div>
);

export default function RemediationsPage() {
  return (
    <ErrorBoundary fallback={pageErrorFallback} boundaryName="RemediationsPage">
      <Suspense fallback={PAGE_FALLBACK}>
        <RemediationsPageInner />
      </Suspense>
    </ErrorBoundary>
  );
}
