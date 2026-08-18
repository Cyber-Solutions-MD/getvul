'use client';
/**
 * /dashboard/campaigns/[id] — CAMP-02 (bulk-create) + CAMP-03 (burndown)
 * campaign detail. Composition mirrors assets/[id]/page.tsx's two-column
 * sticky-rail pattern (page-layouts.md §4):
 *   main   = member-findings table (reuse of the existing per-remediation
 *            hosts endpoint, `GET /vulnerabilities/remediations/{id}/hosts`
 *            — the closest already-shipped "vuln-table chrome filtered to
 *            remediation_id" surface) + a ticket-status breakdown card +
 *            the D-03 live-growth caveat + D-10 new-joiner note.
 *   rail   = CampaignBurndownCard (sticky) + lifecycle actions (Create
 *            tickets / Close campaign).
 *
 * "Create tickets" opens a non-destructive ConfirmModal (provider picker +
 * project key — bulk-assign's `provider`/`project_key` are both REQUIRED,
 * extra="forbid" fields; there is no safe default to silently dispatch
 * against). "Close campaign" opens a destructive ConfirmModal with the
 * exact UI-SPEC confirmation copy, cancel never a bare click.
 *
 * Deviations (documented in 38-05-SUMMARY.md):
 *   - "Un-ticketed members" (the CTA's "Create N tickets" N, and the D-10
 *     note's N) both use CampaignDetail.open — the closest available proxy
 *     (findings still in the raw OPEN status, i.e. never yet ticketed; once
 *     ticketed a finding's status flips to IN_PROGRESS per the ticketing
 *     service). CampaignDetail carries no dedicated "un-ticketed count"
 *     field (Plan 03 didn't add one — same class of gap 38-04-SUMMARY.md
 *     already documented for the list view's MTTR/ticket-count columns).
 *   - The "owner/ticket breakdown card" renders the same open/in_progress/
 *     done counts CampaignDetail already carries (no distinct-owner field
 *     exists on the backend response — identical gap to 38-04's "Tickets"
 *     column deviation).
 */
import { Suspense, useCallback, useState, type ReactNode } from 'react';
import { useParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { Breadcrumb, Crumb } from '@/components/ui/Breadcrumb';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { CampaignStatusRibbon } from '@/components/campaigns/campaign-status-ribbon';
import { CampaignBurndownCard } from '@/components/campaigns/campaign-burndown-card';
import { TicketProviderPicker } from '@/components/vulnerabilities/ticket-provider-picker';
import ConfirmModal from '@/components/ui/ConfirmModal';
import { Input } from '@/components/ui/input';
import {
  SkeletonTable,
  EmptyState,
  PartialFailureBanner,
  type SkeletonColumn,
} from '@/components/states';
import { ErrorBoundary } from '@/components/ui/error-boundary';
import { SEVERITY_GLYPH, SEVERITY_CLASS } from '@/components/tickets/severity-glyph';
import { useCampaignDetail } from '@/lib/queries/use-campaigns';
import { useBulkAssign, useCloseCampaign } from '@/lib/queries/use-campaign-mutations';
import { queryKeys } from '@/lib/queries/keys';
import type { TicketProvider } from '@/lib/ticketing/providers';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';

type MemberHost = {
  asset_id: string;
  hostname: string | null;
  os_name: string | null;
  os_version: string | null;
  cve_id: string | null;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';
  exploit_available: boolean;
  cisa_kev: boolean;
  exploit_status: string | null;
};

const MEMBER_SKELETON_COLUMNS: SkeletonColumn[] = [
  { kind: 'text', width: 20 },
  { kind: 'mono', width: 140 },
  { kind: 'mono', width: 110 },
];

// Singularizes a count string per the zero-one-many gotcha flagged
// throughout 38-UI-SPEC.md ("never '1 findings'").
function countLabel(n: number, singular: string): string {
  return n === 1 ? `1 ${singular}` : `${n} ${singular}s`;
}

function CampaignDetailInner() {
  const { id } = useParams<{ id: string }>();
  useDocumentTitle('Campaign detail');

  const campaign = useCampaignDetail(id);
  const bulkAssign = useBulkAssign();
  const closeCampaign = useCloseCampaign();

  const [closeDialogOpen, setCloseDialogOpen] = useState(false);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [provider, setProvider] = useState<TicketProvider | null>(null);
  const [projectKey, setProjectKey] = useState('');

  const remediationId = campaign.data?.remediation_id ?? null;

  // Member-findings table — reuses the existing per-remediation hosts
  // endpoint (backend/app/vulnerabilities/router.py::hosts_for_remediation),
  // the closest already-shipped "vuln-table chrome filtered to
  // remediation_id" surface. Note this endpoint's own filter
  // (_base_open_vulns) is OPEN/IN_PROGRESS only — rescan-verified REMEDIATED
  // members intentionally drop off this list (same convention as
  // assets/[id]'s AssetVulnsList "No active vulnerabilities" empty copy).
  const members = useQuery({
    queryKey: queryKeys.vulnerabilities.remediationHosts(remediationId ?? ''),
    queryFn: ({ signal }) =>
      api<MemberHost[]>(
        `/api/v1/vulnerabilities/remediations/${encodeURIComponent(remediationId!)}/hosts`,
        { signal },
      ),
    enabled: remediationId !== null,
    staleTime: 30_000,
    retry: 1,
  });

  const onConfirmCreateTickets = useCallback(() => {
    if (!campaign.data || !provider || !projectKey.trim()) return;
    bulkAssign.mutate({
      campaignId: campaign.data.id,
      provider,
      projectKey: projectKey.trim(),
    });
    setCreateDialogOpen(false);
  }, [bulkAssign, campaign.data, provider, projectKey]);

  const onConfirmClose = useCallback(() => {
    if (!campaign.data) return;
    closeCampaign.mutate(campaign.data.id);
    setCloseDialogOpen(false);
  }, [closeCampaign, campaign.data]);

  if (campaign.isLoading) {
    return <SkeletonTable columns={MEMBER_SKELETON_COLUMNS} rows={8} />;
  }

  if (campaign.error || !campaign.data) {
    return (
      <PartialFailureBanner
        errors={[
          {
            code: 'http_error',
            requestId: String((campaign.error as Error)?.message || 'unknown'),
          },
        ]}
        onRetry={() => campaign.refetch()}
      />
    );
  }

  const c = campaign.data;
  const label = c.remediation_id;
  // Deviation: `open` is the closest available proxy for "un-ticketed
  // members" (see module docstring).
  const unticketedCount = c.open;
  // CR-01: a manually- or auto-closed campaign is terminal (matches the
  // "Close campaign" button's own gate below) -- the CTA must not remain
  // enabled once c.status reads 'COMPLETE'.
  const canCreateTickets = unticketedCount > 0 && c.status !== 'COMPLETE';
  const notRescanVerified = c.total - c.done;

  return (
    <>
      <div className="grid grid-cols-1 gap-6 p-6 min-[900px]:grid-cols-[1fr_340px]">
        <section className="space-y-6" aria-label="Campaign details">
          <header className="space-y-2">
            <Breadcrumb>
              <Crumb href="/dashboard/campaigns">Campaigns</Crumb>
              <Crumb>{label}</Crumb>
            </Breadcrumb>
            <div className="flex flex-wrap items-baseline gap-3">
              <h1 className="max-w-2xl truncate font-mono text-2xl text-text" title={label}>
                {label}
              </h1>
              <CampaignStatusRibbon status={c.status} />
            </div>
            {/* D-03 live-growth caveat — verbatim UI-SPEC copy. */}
            <p className="text-sm text-text-muted">
              {countLabel(c.total, 'finding')} currently match this fix — including any
              discovered by later scans.
            </p>
            {/* D-10 new-joiner-untracked note — verbatim UI-SPEC copy shape. */}
            {unticketedCount > 0 && (
              <p className="text-sm text-text-muted">
                {countLabel(unticketedCount, 'newly matched finding')}{' '}
                {unticketedCount === 1 ? "isn't" : "aren't"} ticketed yet.{' '}
                <button
                  type="button"
                  onClick={() => setCreateDialogOpen(true)}
                  className="text-[var(--color-violet-on-soft)] underline underline-offset-2 hover:opacity-80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
                >
                  Create tickets
                </button>
              </p>
            )}
          </header>

          <section aria-label="Campaign members" className="rounded-lg border border-border-subtle">
            {members.isLoading ? (
              <SkeletonTable columns={MEMBER_SKELETON_COLUMNS} rows={5} />
            ) : members.error ? (
              <PartialFailureBanner
                errors={[{ code: 'http_error', requestId: 'members' }]}
                onRetry={() => members.refetch()}
              />
            ) : (members.data ?? []).length === 0 ? (
              <EmptyState>
                <EmptyState.Title>No active members</EmptyState.Title>
                <EmptyState.Body>
                  Every finding in this campaign is either rescan-verified remediated or
                  has no open/in-progress record right now.
                </EmptyState.Body>
              </EmptyState>
            ) : (
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="border-b border-border-subtle text-left text-xs uppercase tracking-wide text-text-muted">
                    <th scope="col" className="px-3 py-2">
                      Severity
                    </th>
                    <th scope="col" className="px-3 py-2">
                      Host
                    </th>
                    <th scope="col" className="px-3 py-2">
                      CVE
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {(members.data ?? []).map((m, idx) => {
                    const sevKey = m.severity.toLowerCase();
                    return (
                      <tr
                        key={`${m.asset_id}-${m.cve_id}-${idx}`}
                        className="border-b border-border-subtle hover:bg-surface-2"
                      >
                        <td className="px-3 py-2">
                          <span
                            role="img"
                            aria-label={m.severity}
                            className={cn('font-mono', SEVERITY_CLASS[sevKey] ?? 'text-text-faint')}
                          >
                            {SEVERITY_GLYPH[sevKey] ?? '□'}
                          </span>
                        </td>
                        <td className="px-3 py-2 font-mono text-text">{m.hostname ?? '—'}</td>
                        <td className="px-3 py-2 font-mono text-text-muted">{m.cve_id ?? '—'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </section>

          {/* Ticket-status breakdown card — same status-family colors as
              the burndown card's breakdown row, never severity colors. */}
          <section
            aria-label="Ticket breakdown"
            className="rounded-lg border border-border-subtle bg-surface-2 p-4"
          >
            <h2 className="text-xs uppercase tracking-wide text-text-muted">Ticket breakdown</h2>
            <div className="mt-2 flex items-center gap-4 font-mono text-sm">
              <span className="text-violet">{c.open} open</span>
              <span className="text-amber">{c.in_progress} in progress</span>
              <span className="text-success">{c.done} done</span>
            </div>
          </section>

          {/* Bulk-create partial-failure banner — amber, never red (the
              campaign itself isn't broken). Rendered only after a bulk-
              assign run that left one or more owners un-ticketed. */}
          {bulkAssign.isSuccess &&
            bulkAssign.data &&
            bulkAssign.data.failed_owners.length > 0 && (
              <PartialFailureBanner
                errors={bulkAssign.data.failed_owners.map((owner) => ({
                  code: 'ticket_create_failed',
                  requestId: owner ?? 'Unassigned',
                }))}
                onRetry={() => setCreateDialogOpen(true)}
              />
            )}
        </section>

        {/* Right rail — sticky at >=900px (matches assets/[id]'s gate). */}
        <aside
          className="space-y-4 min-[900px]:sticky min-[900px]:top-4 min-[900px]:self-start"
          data-testid="campaign-detail-rail"
        >
          <CampaignBurndownCard
            pctRemediated={c.pct_remediated}
            open={c.open}
            inProgress={c.in_progress}
            done={c.done}
            mttrSeconds={c.mttr_seconds}
          />

          <div className="space-y-2 rounded-lg border border-border-subtle bg-surface-2 p-4">
            {canCreateTickets ? (
              <button
                type="button"
                onClick={() => setCreateDialogOpen(true)}
                disabled={bulkAssign.isPending}
                className={cn(
                  'w-full rounded-md bg-gradient-sunset px-4 py-2 text-sm font-medium text-text-inverse shadow-glow-cta',
                  'hover:opacity-95 focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet',
                  'disabled:pointer-events-none disabled:opacity-50',
                )}
              >
                {`Create ${countLabel(unticketedCount, 'ticket')}`}
              </button>
            ) : (
              // Sub-section empty (UI-SPEC): "Every member is already
              // ticketed" inline note, CTA absent — not a full page empty.
              <p className="text-sm text-text-muted">Every member is already ticketed</p>
            )}

            {c.status !== 'COMPLETE' && (
              <button
                type="button"
                onClick={() => setCloseDialogOpen(true)}
                className="w-full rounded-md border border-border-subtle px-4 py-2 text-sm text-text-muted hover:bg-surface hover:text-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
              >
                Close campaign
              </button>
            )}
          </div>
        </aside>
      </div>

      {/* Create tickets — non-destructive; provider/project_key are BOTH
          required fields on the backend (extra="forbid"), so there is no
          safe silent default to dispatch against. */}
      <ConfirmModal
        open={createDialogOpen}
        title="Create tickets"
        message={`Create ${countLabel(unticketedCount, 'ticket')} for this campaign's un-ticketed members, one per owner.`}
        confirmLabel="Create tickets"
        cancelLabel="Cancel"
        variant="info"
        onConfirm={onConfirmCreateTickets}
        onCancel={() => setCreateDialogOpen(false)}
        confirmDisabled={!provider || !projectKey.trim()}
      >
        <div className="space-y-3">
          <TicketProviderPicker value={provider} onChange={setProvider} />
          <Input
            aria-label="Project key"
            placeholder="Project key (e.g. SEC)"
            value={projectKey}
            onChange={(e) => setProjectKey(e.target.value)}
          />
        </div>
      </ConfirmModal>

      {/* Close campaign — destructive, exact UI-SPEC confirmation copy,
          never a bare click. */}
      <ConfirmModal
        open={closeDialogOpen}
        title="Close campaign"
        message={`Close "${label}" early? ${notRescanVerified} of ${c.total} findings aren't rescan-verified yet — they'll stop being tracked here. This can't be undone from the campaign view.`}
        confirmLabel="Close campaign"
        cancelLabel="Cancel"
        variant="danger"
        onConfirm={onConfirmClose}
        onCancel={() => setCloseDialogOpen(false)}
      />
    </>
  );
}

function pageErrorFallback(err: Error, reset: () => void): ReactNode {
  return (
    <div className="space-y-4 p-6">
      <h1 className="sr-only">Campaign detail</h1>
      <PartialFailureBanner
        errors={[{ code: 'crash', requestId: err.message || 'unknown' }]}
        onRetry={reset}
      />
    </div>
  );
}

const PAGE_FALLBACK = (
  <div className="p-6">
    <SkeletonTable columns={MEMBER_SKELETON_COLUMNS} rows={8} />
  </div>
);

export default function CampaignDetailPage() {
  return (
    <ErrorBoundary fallback={pageErrorFallback} boundaryName="CampaignDetailPage">
      <Suspense fallback={PAGE_FALLBACK}>
        <CampaignDetailInner />
      </Suspense>
    </ErrorBoundary>
  );
}
