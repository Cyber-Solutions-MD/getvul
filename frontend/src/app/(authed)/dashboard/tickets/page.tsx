'use client';
/**
 * /tickets — UX-05-01/02/03/06 list page (sunset rewrite — v1 fully replaced).
 *
 * Composition mirrors assets/page.tsx:
 *   ErrorBoundary > Suspense > TicketsPageInner
 *
 * State branches (mutually exclusive, WR-13):
 *   q.error → PartialFailureBanner (full message, WR-10)
 *   isLoading → SkeletonTable
 *   items.length === 0 → EmptyState (connector deep-link variant for Asana, D-S-02)
 *   else → TicketsTable + Pagination
 *
 * List/Board segmented toggle (D-L-03) persists in ?view URL param.
 * Board branch renders TicketsKanbanBoard (Phase 18, UX-D-01-01..06),
 * lazily imported via next/dynamic({ssr:false}) to keep @dnd-kit out of
 * this route's First-Load JS.
 * Drill via DrillPanel(idKey="ticket") + DrillPanelMobile (D-D-02).
 * Bulk bar wired to TicketBulkBar selection (D-S-03).
 *
 * T-13-22: XSS allow-lists mirror the chip-bar (module-scope constants).
 * WR-10: full err.message passed to PartialFailureBanner — no slice.
 * Zero v1 carryover: AsanaSetupModal / TicketBulkActions / RulesPanel / CommentModal absent.
 * No inline hex — all colors via Tailwind sunset tokens.
 */
import { Suspense, useCallback, useMemo, useState, type ReactNode } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import dynamic from 'next/dynamic';
import Link from 'next/link';
import { TicketsChipBar } from '@/components/tickets/tickets-chip-bar';
import { TicketsTable } from '@/components/tickets/tickets-table';
import { TicketBulkBar, type BulkAction } from '@/components/tickets/ticket-bulk-bar';
import { TicketDrillContent } from '@/components/tickets/ticket-drill-content';
import { BlockedToggle } from '@/components/tickets/blocked-toggle';
import {
  SkeletonTable,
  EmptyState,
  PartialFailureBanner,
  type SkeletonColumn,
} from '@/components/states';
import Pagination from '@/components/ui/Pagination';
import { ErrorBoundary } from '@/components/ui/error-boundary';
import { DrillPanel } from '@/components/vulnerabilities/drill-panel';
import { DrillPanelMobile } from '@/components/vulnerabilities/drill-panel-mobile';
import { useUrlState } from '@/hooks/use-url-state';
import { useUrlStateList } from '@/hooks/use-url-state-list';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { useTickets, type TicketSummary, type TicketsFilters } from '@/lib/queries/use-tickets';
import { useMarkBlocked } from '@/lib/queries/use-mark-blocked';
import { api } from '@/lib/api';

// XSS allow-lists mirror TicketsChipBar (T-13-22). Module-scope for stable references.
const STATUS_ALLOW = ['open', 'in_progress', 'completed', 'blocked'] as const;
const PROVIDER_ALLOW = ['jira', 'asana', 'github'] as const;
const SEVERITY_ALLOW = ['critical', 'high', 'medium', 'low'] as const;
const SLA_ALLOW = ['overdue', 'soon', 'ok'] as const;
const VIEW_ALLOW = ['list', 'board'] as const;
type View = (typeof VIEW_ALLOW)[number];

// CR-06: narrow the backend-lowercased provider string to the literal union
// without an unchecked `as` cast.
function isTicketProvider(v: string | null): v is 'jira' | 'asana' | 'github' {
  return v === 'jira' || v === 'asana' || v === 'github';
}

// 8-column skeleton shape mirrors TicketsTable. Module-scope = stable reference.
const SKELETON_COLUMNS: SkeletonColumn[] = [
  { kind: 'mono', width: 24 },   // checkbox
  { kind: 'text', width: 20 },   // severity glyph
  { kind: 'badge', width: 24 },  // provider mark
  { kind: 'mono', width: 80 },   // ID
  { kind: 'text', width: 220 },  // title
  { kind: 'text', width: 60 },   // vulns
  { kind: 'text', width: 100 },  // assignee
  { kind: 'badge', width: 70 },  // status
  { kind: 'mono', width: 60 },   // SLA
];

// UX-D-01-06: lazy-load the board so @dnd-kit stays out of this route's
// First-Load JS (Pitfall 5) — the route must stay <=250 KB.
const TicketsKanbanBoard = dynamic(
  () => import('./tickets-kanban-board').then((m) => m.TicketsKanbanBoard),
  { ssr: false, loading: () => <SkeletonTable columns={SKELETON_COLUMNS} rows={6} /> },
);

function isAsanaNotConfigured(error: Error | null): boolean {
  if (!error) return false;
  const msg = error.message?.toLowerCase() ?? '';
  return (
    msg.includes('asana_not_configured') ||
    msg.includes('asana not configured') ||
    (msg.includes('asana') && msg.includes('connector'))
  );
}

function pageErrorFallback(err: Error, reset: () => void): ReactNode {
  return (
    <div className="space-y-4 p-6">
      <h1 className="sr-only">Tickets</h1>
      <PartialFailureBanner
        errors={[{ code: 'crash', requestId: err.message || 'unknown' }]}
        onRetry={reset}
      />
    </div>
  );
}

function TicketsPageInner() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  useDocumentTitle('Tickets');

  // URL filter state — each axis uses its allow-list for XSS clamp (T-13-22).
  const [status] = useUrlStateList<string>('status', STATUS_ALLOW, []);
  const [provider] = useUrlStateList<string>('provider', PROVIDER_ALLOW, []);
  const [severity] = useUrlStateList<string>('severity', SEVERITY_ALLOW, []);
  const [sla] = useUrlStateList<string>('sla', SLA_ALLOW, []);
  const [view, setView] = useUrlState<View>('view', VIEW_ALLOW, 'list');
  const search = params?.get('search') ?? '';
  const pageNum = Math.max(1, Number(params?.get('page') ?? '1') || 1);

  // Ticket id from URL for drill panel.
  const ticketIdFromUrl = params?.get('ticket') ?? null;

  // Memoize filters for stable TanStack cache key.
  const filters: TicketsFilters = useMemo(
    () => ({
      status: status.length ? status : undefined,
      provider: provider.length ? provider : undefined,
      severity: severity.length ? severity : undefined,
      sla: sla.length ? sla : undefined,
      search: search || undefined,
    }),
    [status, provider, severity, sla, search],
  );

  const q = useTickets({ filters, page: pageNum, view });
  const markBlocked = useMarkBlocked();

  // Selection state for bulk bar.
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Find the selected ticket for the drill panel (list row supplies the data).
  const selectedTicket: TicketSummary | undefined = useMemo(
    () =>
      q.data?.items.find((t) => t.id === ticketIdFromUrl) ?? undefined,
    [q.data?.items, ticketIdFromUrl],
  );

  // Row click → set ?ticket=<id>&open=drill (D-D-02).
  const onRowClick = useCallback(
    (ticket: TicketSummary) => {
      const sp = new URLSearchParams(params?.toString() ?? '');
      sp.set('ticket', ticket.id);
      sp.set('open', 'drill');
      const qs = sp.toString();
      router.replace(qs ? `${pathname}?${qs}` : (pathname ?? '/'), { scroll: false });
    },
    [router, pathname, params],
  );

  const handlePageChange = useCallback(
    (next: number) => {
      const sp = new URLSearchParams(params?.toString() ?? '');
      if (next <= 1) sp.delete('page');
      else sp.set('page', String(next));
      const qs = sp.toString();
      router.replace(qs ? `${pathname}?${qs}` : (pathname ?? '/'), { scroll: false });
    },
    [router, pathname, params],
  );

  // Bulk action handler → POST /tickets/bulk-action.
  const handleBulkAction = useCallback(
    async (action: BulkAction, blockedReason?: string | null) => {
      const urls = q.data?.items
        .filter((t) => selectedIds.has(t.id))
        .map((t) => t.external_ticket_url) ?? [];
      if (urls.length === 0) return;
      try {
        await api('/api/v1/tickets/bulk-action', {
          method: 'POST',
          body: JSON.stringify({
            action,
            // CR-01: router.py reads body.get("ticket_urls"); the key MUST be
            // ticket_urls or every bulk action 400s ("No tickets selected").
            ticket_urls: urls,
            blocked_reason: blockedReason ?? null,
          }),
          headers: { 'Content-Type': 'application/json' },
        });
        setSelectedIds(new Set());
        q.refetch();
      } catch {
        // Errors bubble to toast via api.ts error handling.
      }
    },
    [q, selectedIds],
  );

  const isLoading = q.isPending;
  const items = q.data?.items ?? [];
  const total = q.data?.total ?? 0;
  const asanaUnconfigured = isAsanaNotConfigured(q.error as Error | null);

  return (
    <div className="space-y-4 p-6">
      <header className="flex items-start justify-between">
        <div className="space-y-1">
          <div className="text-xs uppercase tracking-wide text-text-muted">
            Tickets · {total} {total === 1 ? 'ticket' : 'tickets'}
          </div>
          <h1 className="text-2xl font-semibold text-text">Tickets</h1>
        </div>

        {/* List/Board segmented toggle (D-L-03) */}
        <div
          role="group"
          aria-label="View mode"
          className="inline-flex rounded-lg border border-border-subtle bg-surface-2 p-0.5"
        >
          <button
            type="button"
            onClick={() => setView('list')}
            aria-pressed={view === 'list'}
            className={
              view === 'list'
                ? 'rounded-md bg-surface px-3 py-1.5 text-sm font-medium text-text shadow-sm'
                : 'rounded-md px-3 py-1.5 text-sm font-medium text-text-muted hover:text-text'
            }
          >
            List
          </button>
          <button
            type="button"
            onClick={() => setView('board')}
            aria-pressed={view === 'board'}
            className={
              view === 'board'
                ? 'rounded-md bg-surface px-3 py-1.5 text-sm font-medium text-text shadow-sm'
                : 'rounded-md px-3 py-1.5 text-sm font-medium text-text-muted hover:text-text'
            }
          >
            Board
          </button>
        </div>
      </header>

      <TicketsChipBar />

      {/* WR-03: asana_not_configured is an EXPECTED "connector unconfigured"
          signal, not a transient failure — route it to the connector deep-link
          EmptyState (D-S-02) BEFORE the list/board switch so both views get the
          same remediation CTA instead of an opaque error banner. */}
      {asanaUnconfigured ? (
        <EmptyState>
          <EmptyState.Title>Set up a ticket connector</EmptyState.Title>
          <EmptyState.Body>
            Connect Jira, Asana, or GitHub to start tracking remediation tickets.
          </EmptyState.Body>
          <EmptyState.Actions>
            <Link
              href="/dashboard/connectors"
              className="inline-flex items-center gap-1.5 rounded-md bg-gradient-sunset px-4 py-2 text-sm font-medium text-text-inverse shadow-glow-cta hover:opacity-95 focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
            >
              Set up connectors →
            </Link>
          </EmptyState.Actions>
        </EmptyState>
      ) : view === 'board' ? (
        /* Board view — real kanban (D-L-03, UX-D-01-01..06) */
        <>
          <TicketsKanbanBoard
            rows={items}
            isLoading={isLoading}
            error={q.error as Error | null}
            onOpen={onRowClick}
            onRetry={() => q.refetch()}
          />
          {/* WR-01: the board buckets only the current page. Surface the same
              Pagination control the list uses so tickets beyond page 1 (e.g. a
              Blocked ticket on page 2) are reachable and can be dragged. */}
          {(q.data?.pages ?? 1) > 1 && (
            <Pagination
              page={pageNum}
              totalPages={q.data?.pages ?? 1}
              total={q.data?.total ?? 0}
              pageSize={q.data?.page_size ?? 25}
              onPageChange={handlePageChange}
            />
          )}
        </>
      ) : (
        <>
          {/* WR-13: state branches are mutually exclusive.
              (asana_not_configured is handled above, before this switch — WR-03.)
              Other errors → PartialFailureBanner.
              isLoading → skeleton. items.length === 0 → EmptyState. else → table. */}
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
              <EmptyState.Title>No tickets match these filters</EmptyState.Title>
              <EmptyState.Body>
                Adjust the chip-bar filters or clear them to see all tickets.
              </EmptyState.Body>
            </EmptyState>
          ) : (
            <>
              <TicketsTable
                rows={items}
                onRowClick={onRowClick}
                selectedIds={selectedIds}
                onSelectionChange={setSelectedIds}
              />
              {(q.data?.pages ?? 1) > 1 && (
                <Pagination
                  page={pageNum}
                  totalPages={q.data?.pages ?? 1}
                  total={q.data?.total ?? 0}
                  pageSize={q.data?.page_size ?? 25}
                  onPageChange={handlePageChange}
                />
              )}
            </>
          )}
        </>
      )}

      {/* Drill panel — desktop (D-D-02, idKey="ticket") */}
      <DrillPanel
        idKey="ticket"
        id={ticketIdFromUrl}
        ariaLabel="Ticket detail"
        renderContent={({ id, onClose }) => (
          <TicketDrillContent
            ticketId={id}
            ticket={
              selectedTicket
                ? {
                    // CR-06: provider is backend-lowercased; validate rather than
                    // launder via `as`. Falls back to 'jira' only if somehow off-list.
                    provider: (isTicketProvider(selectedTicket.provider)
                      ? selectedTicket.provider
                      : 'jira'),
                    externalId: selectedTicket.external_ticket_id,
                    title: selectedTicket.title,
                    externalUrl: selectedTicket.external_ticket_url,
                    externalStatus: selectedTicket.external_status,
                    blocked: selectedTicket.blocked,
                    slaDueAt: selectedTicket.sla_due_at,
                    description: null,
                    linkedVulns: [],
                    totalVulns: selectedTicket.vuln_count,
                  }
                : undefined
            }
            onClose={onClose}
            renderBlockedToggle={({ ticketId }) => (
              <BlockedToggle
                blocked={selectedTicket?.blocked ?? false}
                blockedReason={selectedTicket?.blocked_reason ?? null}
                pending={markBlocked.isPending}
                onToggle={(next) =>
                  markBlocked.mutate({
                    id: ticketId,
                    blocked: next.blocked,
                    blocked_reason: next.blockedReason,
                  })
                }
              />
            )}
          />
        )}
      />

      {/* Drill panel — mobile (D-D-03) */}
      <DrillPanelMobile
        idKey="ticket"
        id={ticketIdFromUrl}
        ariaLabel="Ticket detail"
        renderContent={({ id, onClose }) => (
          <TicketDrillContent
            ticketId={id}
            ticket={
              selectedTicket
                ? {
                    // CR-06: provider is backend-lowercased; validate rather than
                    // launder via `as`. Falls back to 'jira' only if somehow off-list.
                    provider: (isTicketProvider(selectedTicket.provider)
                      ? selectedTicket.provider
                      : 'jira'),
                    externalId: selectedTicket.external_ticket_id,
                    title: selectedTicket.title,
                    externalUrl: selectedTicket.external_ticket_url,
                    externalStatus: selectedTicket.external_status,
                    blocked: selectedTicket.blocked,
                    slaDueAt: selectedTicket.sla_due_at,
                    description: null,
                    linkedVulns: [],
                    totalVulns: selectedTicket.vuln_count,
                  }
                : undefined
            }
            onClose={onClose}
            renderBlockedToggle={({ ticketId }) => (
              <BlockedToggle
                blocked={selectedTicket?.blocked ?? false}
                blockedReason={selectedTicket?.blocked_reason ?? null}
                pending={markBlocked.isPending}
                onToggle={(next) =>
                  markBlocked.mutate({
                    id: ticketId,
                    blocked: next.blocked,
                    blocked_reason: next.blockedReason,
                  })
                }
              />
            )}
          />
        )}
      />

      {/* Bulk bar — appears on selection (D-S-03) */}
      <TicketBulkBar
        selectedCount={selectedIds.size}
        onBulkAction={handleBulkAction}
        onClearSelection={() => setSelectedIds(new Set())}
        isPending={false}
      />
    </div>
  );
}

const PAGE_FALLBACK = (
  <div className="space-y-4 p-6">
    <h1 className="sr-only">Tickets</h1>
    <SkeletonTable columns={SKELETON_COLUMNS} rows={10} />
  </div>
);

export default function TicketsPage() {
  return (
    <ErrorBoundary fallback={pageErrorFallback} boundaryName="TicketsPage">
      <Suspense fallback={PAGE_FALLBACK}>
        <TicketsPageInner />
      </Suspense>
    </ErrorBoundary>
  );
}
