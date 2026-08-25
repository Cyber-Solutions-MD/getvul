'use client';
/**
 * /campaigns — CAMP-01 dedicated campaign list view.
 *
 * Composition mirrors tickets/page.tsx:
 *   ErrorBoundary > Suspense > CampaignsPageInner
 *
 * State branches (mutually exclusive, WR-13):
 *   q.error -> PartialFailureBanner (full message, WR-10)
 *   isLoading -> SkeletonTable
 *   items.length === 0 -> EmptyState ("No campaigns yet" + "View remediation
 *     groups" CTA, per 38-UI-SPEC.md's Copywriting Contract)
 *   else -> CampaignsTable
 *
 * Status filtering (Active/Complete) is CLIENT-SIDE: GET /api/v1/campaigns
 * has no server-side status query param (D-07 always returns the full
 * tenant-scoped list; see campaigns/router.py::campaigns_list) — unlike
 * tickets' server-filtered `?status=`. The chip-bar's `status` URL state is
 * read here and used to filter the fetched array in-memory.
 *
 * Row click -> full navigation to /dashboard/campaigns/{id} (the Plan 05
 * campaign detail page), per UI-SPEC Layout & Interaction Reuse item 2's
 * "planner's discretion" resolved to full navigation, not a drill panel.
 * CampaignsTable never calls useRouter itself — this page owns navigation
 * and passes it down via the onRowClick prop.
 *
 * "View remediation groups" links to /dashboard/vulnerabilities/remediations
 * (Plan 05's entry-point page, per UI-SPEC). That route does not exist until
 * Plan 05 ships — expected within this same phase's execution sequence, see
 * 38-04-SUMMARY.md.
 */
import { Suspense, useCallback, useMemo, type ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { CampaignsChipBar } from '@/components/campaigns/campaigns-chip-bar';
import { CampaignsTable } from '@/components/campaigns/campaigns-table';
import {
  SkeletonTable,
  EmptyState,
  PartialFailureBanner,
  type SkeletonColumn,
} from '@/components/states';
import { ErrorBoundary } from '@/components/ui/error-boundary';
import { useUrlStateList } from '@/hooks/use-url-state-list';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { useCampaigns, type CampaignSummary } from '@/lib/queries/use-campaigns';

// Mirrors CampaignsChipBar's STATUS_ALLOW (T-38-09/T-12-05 allow-list clamp).
const STATUS_ALLOW = ['ACTIVE', 'COMPLETE'] as const;

// 6-column skeleton shape mirrors CampaignsTable.
const SKELETON_COLUMNS: SkeletonColumn[] = [
  { kind: 'mono', width: 220 }, // remediation
  { kind: 'text', width: 90 }, // members
  { kind: 'mono', width: 50 }, // % remediated
  { kind: 'mono', width: 40 }, // MTTR
  { kind: 'badge', width: 70 }, // status
  { kind: 'text', width: 70 }, // tickets
];

function pageErrorFallback(err: Error, reset: () => void): ReactNode {
  return (
    <div className="space-y-4 p-6">
      <h1 className="sr-only">Campaigns</h1>
      <PartialFailureBanner
        errors={[{ code: 'crash', requestId: err.message || 'unknown' }]}
        onRetry={reset}
      />
    </div>
  );
}

function CampaignsPageInner() {
  const router = useRouter();
  useDocumentTitle('Campaigns');

  const [status] = useUrlStateList<string>('status', STATUS_ALLOW, []);

  const q = useCampaigns();

  const items = useMemo(() => {
    const all = q.data ?? [];
    if (status.length === 0) return all;
    return all.filter((c) => status.includes(c.status));
  }, [q.data, status]);

  // Row click -> full navigation. CampaignsTable never calls useRouter
  // itself — the page owns navigation per UI-SPEC's explicit contract.
  const onRowClick = useCallback(
    (campaign: CampaignSummary) => {
      router.push(`/dashboard/campaigns/${campaign.id}`);
    },
    [router],
  );

  const isLoading = q.isPending;

  return (
    <div className="space-y-4 p-6">
      <header className="space-y-1">
        <div className="text-xs uppercase tracking-wide text-text-muted">
          Campaigns · {items.length} {items.length === 1 ? 'campaign' : 'campaigns'}
        </div>
        <h1 className="text-2xl font-semibold text-text">Campaigns</h1>
      </header>

      <CampaignsChipBar />

      {/* WR-13: state branches are mutually exclusive — error > loading > empty > data. */}
      {q.error ? (
        <PartialFailureBanner
          errors={[
            {
              code: 'http_error',
              // WR-10: pass full message; banner truncates visually.
              requestId: String((q.error as Error).message) || 'unknown',
            },
          ]}
          onRetry={() => q.refetch()}
        />
      ) : isLoading ? (
        <SkeletonTable columns={SKELETON_COLUMNS} rows={10} />
      ) : items.length === 0 ? (
        <EmptyState>
          <EmptyState.Title>No campaigns yet</EmptyState.Title>
          <EmptyState.Body>
            Group findings that share a fix into a campaign from the
            Remediations view, and bulk-create tickets in one action instead
            of ticketing hosts one at a time.
          </EmptyState.Body>
          <EmptyState.Actions>
            <Link
              href="/dashboard/vulnerabilities/remediations"
              className="inline-flex items-center gap-1.5 rounded-md bg-gradient-sunset px-4 py-2 text-sm font-medium text-text-inverse shadow-glow-cta hover:opacity-95 focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
            >
              View remediation groups
            </Link>
          </EmptyState.Actions>
        </EmptyState>
      ) : (
        <CampaignsTable rows={items} onRowClick={onRowClick} />
      )}
    </div>
  );
}

const PAGE_FALLBACK = (
  <div className="space-y-4 p-6">
    <h1 className="sr-only">Campaigns</h1>
    <SkeletonTable columns={SKELETON_COLUMNS} rows={10} />
  </div>
);

export default function CampaignsPage() {
  return (
    <ErrorBoundary fallback={pageErrorFallback} boundaryName="CampaignsPage">
      <Suspense fallback={PAGE_FALLBACK}>
        <CampaignsPageInner />
      </Suspense>
    </ErrorBoundary>
  );
}
