'use client';
/**
 * /tickets/[id] — UX-05-04/05 two-column ticket detail page.
 *
 * Layout (>=900px) — CLONED from assets/[id]/page.tsx skeleton:
 *   +----------------------+ rail 340px +
 *   | Breadcrumb           | Details    |  StatusPill + SlaPill + BlockedToggle
 *   | H1 title + pills     | People     |  assignee + reporter + WatcherStack + Watch
 *   | Linked vulns         | Asset      |  TicketAssetCard → /assets/{id}
 *   | Description          |            |
 *   | ActivityTimeline     |            |
 *   | CommentInput         |            |
 *   +----------------------+------------+
 *
 * Layout (<900px): rail stacks below main column.
 *
 * State branches (mutually exclusive — WR-13):
 *   isLoading        → <SkeletonTable />
 *   404 / no data    → <EmptyState> not-found (links back to /tickets)
 *   other error      → <PartialFailureBanner> with FULL err.message (WR-10/15 — no .slice)
 *   else             → full two-column layout
 *
 * O1 identity: the `id` param is the canonical `first_ticket_id` group key.
 * The backend `_resolve_group` maps it; the frontend passes it verbatim.
 *
 * Security:
 *   - T-13-26: only {body} posted for comments; watch sends no body (method only).
 *   - T-13-27: description + comment bodies rendered as React text nodes (whitespace-pre-wrap).
 *     innerHTML usage is absent — XSS via user content is prevented.
 *   - No inline hex — all colors via Tailwind sunset tokens.
 *   - WR-10/15: FULL err.message to PartialFailureBanner (no .slice, no .substring).
 */
import { Suspense } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { Eye, EyeOff } from 'lucide-react';
import { Breadcrumb, Crumb } from '@/components/ui/Breadcrumb';
import { Avatar } from '@/components/ui/Avatar';
import { ProviderMark } from '@/components/tickets/provider-mark';
import { StatusPill } from '@/components/tickets/status-pill';
import { SlaPill } from '@/components/tickets/sla-pill';
import { WatcherStack, type Watcher } from '@/components/tickets/watcher-stack';
import { ActivityTimeline, type TimelineEntry } from '@/components/tickets/activity-timeline';
import { CommentInput } from '@/components/tickets/comment-input';
import { BlockedToggle } from '@/components/tickets/blocked-toggle';
import { TicketAssetCard } from '@/components/tickets/ticket-asset-card';
import {
  SkeletonTable,
  EmptyState,
  PartialFailureBanner,
  type SkeletonColumn,
} from '@/components/states';
import { ErrorBoundary } from '@/components/ui/error-boundary';
import { useTicketDetail } from '@/lib/queries/use-ticket-detail';
import { useTicketComments, useAddComment } from '@/lib/queries/use-ticket-comments';
import { useTicketWatch } from '@/lib/queries/use-ticket-watch';
import { useMarkBlocked } from '@/lib/queries/use-mark-blocked';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { useAuth } from '@/lib/auth';

// ---------------------------------------------------------------------------
// Skeleton columns — mirrors assets/[id] shape (pill + mono + text + score)
// ---------------------------------------------------------------------------
const SKELETON_COLUMNS: SkeletonColumn[] = [
  { kind: 'pill', width: 24 },
  { kind: 'mono', width: 130 },
  { kind: 'text', width: 280 },
  { kind: 'mono', width: 50 },
];

// ---------------------------------------------------------------------------
// Severity glyph map (visual-language.md — no raw hex; colors via tokens)
// ---------------------------------------------------------------------------
const SEVERITY_GLYPH: Record<string, { glyph: string; className: string }> = {
  critical: { glyph: '■', className: 'text-[var(--color-severity-critical-on-soft)]' },
  high:     { glyph: '▲', className: 'text-[var(--color-severity-high-on-soft)]' },
  medium:   { glyph: '◆', className: 'text-severity-medium' },
  low:      { glyph: '○', className: 'text-severity-low' },
};

function severityGlyph(severity: string | null) {
  const key = (severity ?? '').toLowerCase();
  return SEVERITY_GLYPH[key] ?? { glyph: '□', className: 'text-text-muted' };
}

// ---------------------------------------------------------------------------
// Helper: map comments to TimelineEntry[]
// ---------------------------------------------------------------------------
function mapCommentsToEntries(
  comments: Array<{
    id: string;
    user_display_name: string | null;
    body: string;
    created_at: string;
  }>,
): TimelineEntry[] {
  // CR-05: read snake_case (user_display_name / created_at) — the wire shape.
  return comments.map((c) => ({
    kind: 'comment' as const,
    id: c.id,
    author: c.user_display_name,
    body: c.body,
    createdAt: c.created_at,
  }));
}

// ---------------------------------------------------------------------------
// Helper: build role-tagged watcher list per D-W-04.
// Merge assignee + reporter + watchers; dedupe by userId (strongest role wins:
// assignee > reporter > watcher); sort assignee → reporter → watcher (chrono).
// ---------------------------------------------------------------------------
type WithRole = Watcher & { role: NonNullable<Watcher['role']> };

const ROLE_PRIORITY: Record<NonNullable<Watcher['role']>, number> = {
  assignee: 0,
  reporter: 1,
  watcher: 2,
};

function buildWatcherList(params: {
  assignee: { userId: string; displayName: string; email?: string } | null;
  reporter: { userId: string; displayName: string; email?: string } | null;
  watchers: Watcher[];
}): Watcher[] {
  const map = new Map<string, WithRole>();

  function addEntry(entry: WithRole) {
    const existing = map.get(entry.userId);
    if (!existing || ROLE_PRIORITY[entry.role] < ROLE_PRIORITY[existing.role]) {
      map.set(entry.userId, entry);
    }
  }

  if (params.assignee) {
    addEntry({ ...params.assignee, role: 'assignee' });
  }
  if (params.reporter) {
    addEntry({ ...params.reporter, role: 'reporter' });
  }
  for (const w of params.watchers) {
    addEntry({ ...w, role: (w.role ?? 'watcher') as NonNullable<Watcher['role']> });
  }

  return Array.from(map.values()).sort((a, b) => {
    const pa = ROLE_PRIORITY[a.role as NonNullable<Watcher['role']>] ?? 2;
    const pb = ROLE_PRIORITY[b.role as NonNullable<Watcher['role']>] ?? 2;
    if (pa !== pb) return pa - pb;
    const ta = a.createdAt ?? '';
    const tb = b.createdAt ?? '';
    return ta.localeCompare(tb);
  });
}

// ---------------------------------------------------------------------------
// Inner component (rendered inside ErrorBoundary > Suspense)
// ---------------------------------------------------------------------------

function TicketDetailInner() {
  const { id } = useParams<{ id: string }>();

  // WR-06: source the real current-user id from the auth context (useAuth).
  // The watch-toggle uses it to patch the watchers array optimistically and to
  // compute isWatching. Empty string only if the session somehow lacks a user
  // (the (authed) layout already gates unauthenticated access).
  const { user } = useAuth();
  const currentUserId = user?.id ?? '';

  const detail = useTicketDetail(id);
  const comments = useTicketComments(id);
  const watch = useTicketWatch(id ?? '', currentUserId);
  // REUSE useMarkBlocked from 13-07 — do NOT redefine it here.
  const markBlocked = useMarkBlocked();
  const addComment = useAddComment(id ?? '');

  useDocumentTitle(detail.data?.title ?? 'Ticket detail');

  // --- State branches (mutually exclusive — WR-13) ---

  if (detail.isLoading) {
    return <SkeletonTable columns={SKELETON_COLUMNS} rows={8} />;
  }

  if (detail.error || !detail.data) {
    const errMsg = (detail.error as Error)?.message ?? '';
    const is404 =
      errMsg.includes('404') ||
      errMsg.toLowerCase().includes('not found') ||
      !detail.data;

    if (is404) {
      return (
        <EmptyState>
          <EmptyState.Title>Ticket not found</EmptyState.Title>
          <EmptyState.Body>
            This ticket doesn&apos;t exist or you don&apos;t have access to it.{' '}
            <Link href="/dashboard/tickets" className="text-[var(--color-violet-on-soft)] hover:underline">
              Back to tickets
            </Link>
          </EmptyState.Body>
        </EmptyState>
      );
    }

    return (
      <PartialFailureBanner
        errors={[
          {
            code: 'http_error',
            // WR-10/15: full err.message — NO .slice or .substring.
            requestId: String((detail.error as Error)?.message || 'unknown'),
          },
        ]}
        onRetry={() => detail.refetch()}
      />
    );
  }

  const t = detail.data;
  const commentList = comments.data ?? [];
  const timelineEntries = mapCommentsToEntries(commentList);

  // Build role-tagged watcher list for WatcherStack (D-W-04).
  const watcherList = buildWatcherList({
    assignee: t.assignee,
    reporter: t.reporter,
    watchers: t.watchers,
  });

  // Is current user already watching? (WR-06: compares real user id.)
  const isWatching =
    !!currentUserId && t.watchers.some((w) => w.userId === currentUserId);

  // W7: explicit 900px gate mirrors assets/[id] and Phase 11 D-P-03 threshold
  return (
    <div className="grid grid-cols-1 gap-6 p-6 min-[900px]:grid-cols-[1fr_340px]">
      {/* ------------------------------------------------------------------ */}
      {/* Main column — semantically a section, NOT a <main> (BL-03) */}
      {/* ------------------------------------------------------------------ */}
      <section className="space-y-6" aria-label="Ticket details">
        {/* Header: Breadcrumb + H1 + status pills */}
        <header className="space-y-2">
          <Breadcrumb>
            <Crumb href="/dashboard/tickets">Tickets</Crumb>
            <Crumb>{t.title}</Crumb>
          </Breadcrumb>

          <div className="flex flex-wrap items-center gap-2">
            <ProviderMark provider={t.provider} />
            <h1 className="text-xl font-semibold text-text">{t.title}</h1>
          </div>

          {/* Status pills row */}
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill externalStatus={t.external_status} blocked={t.blocked} />
            <SlaPill dueAt={t.sla_due_at} />
          </div>
        </header>

        {/* Linked vulnerabilities */}
        <section aria-label="Linked vulnerabilities" className="space-y-2">
          <h2 className="text-sm uppercase tracking-wide text-text-muted">
            Linked vulnerabilities
          </h2>
          {t.linked_vulns.length === 0 ? (
            <EmptyState>
              <EmptyState.Title>No linked vulnerabilities</EmptyState.Title>
              <EmptyState.Body>
                No vulnerabilities are linked to this ticket yet.
              </EmptyState.Body>
            </EmptyState>
          ) : (
            <ul className="space-y-1">
              {t.linked_vulns.map((v) => {
                const { glyph, className } = severityGlyph(v.severity);
                return (
                  <li
                    key={v.cve}
                    className="flex items-center gap-3 rounded-lg border border-border-subtle bg-surface-2 px-3 py-2 text-sm"
                  >
                    {/* Severity glyph — color via token, no raw hex */}
                    <span className={`font-mono text-xs ${className}`} aria-label={v.severity ?? undefined}>
                      {glyph}
                    </span>
                    {/* CVE ID — mono per design system (terminal-pasteable) */}
                    <span className="font-mono text-text">{v.cve}</span>
                    {/* CVSS score */}
                    {v.cvss !== null && (
                      <span className="font-mono text-xs text-text-muted ml-auto">
                        {v.cvss.toFixed(1)}
                      </span>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        {/* Description — plain text node, whitespace-pre-wrap, NO innerHTML */}
        {t.description && (
          <section aria-label="Description" className="space-y-1">
            <h2 className="text-sm uppercase tracking-wide text-text-muted">Description</h2>
            {/* T-13-27: whitespace-pre-wrap + React text node = XSS-safe */}
            <p className="whitespace-pre-wrap text-sm text-text-muted">{t.description}</p>
          </section>
        )}

        {/* Activity timeline + comment input (D-C-04: CommentInput BELOW timeline) */}
        <section aria-label="Activity" className="space-y-2">
          <h2 className="text-sm uppercase tracking-wide text-text-muted">Activity</h2>
          <ActivityTimeline entries={timelineEntries} />
          <CommentInput
            onSubmit={(body) => addComment.mutate(body)}
            submitting={addComment.isPending}
          />
        </section>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* Right rail — sticky at >=900px */}
      {/* ------------------------------------------------------------------ */}
      <aside
        className="space-y-4 min-[900px]:sticky min-[900px]:top-4 min-[900px]:self-start"
        data-testid="ticket-detail-rail"
      >
        {/* Details card: StatusPill + SlaPill + BlockedToggle (D-P-03) */}
        <div className="rounded-xl border border-border-subtle bg-surface-2 p-4 space-y-3">
          <h3 className="text-xs uppercase tracking-wide text-text-muted font-medium">Details</h3>
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill externalStatus={t.external_status} blocked={t.blocked} />
            <SlaPill dueAt={t.sla_due_at} />
          </div>
          {/* BlockedToggle — inline editor per D-P-03; reuses 13-07 useMarkBlocked */}
          <BlockedToggle
            blocked={t.blocked}
            blockedReason={t.blocked_reason}
            pending={markBlocked.isPending}
            onToggle={(next) =>
              markBlocked.mutate({
                id: id ?? '',
                blocked: next.blocked,
                blocked_reason: next.blockedReason,
              })
            }
          />
        </div>

        {/* People card: assignee + reporter + WatcherStack + Watch/Watching toggle */}
        <div className="rounded-xl border border-border-subtle bg-surface-2 p-4 space-y-3">
          <h3 className="text-xs uppercase tracking-wide text-text-muted font-medium">People</h3>

          {/* Assignee row */}
          <div className="flex items-center gap-2 text-sm">
            <span className="text-xs text-text-muted w-16 shrink-0">Assignee</span>
            {t.assignee ? (
              <>
                <Avatar name={t.assignee.displayName} email={t.assignee.email} size={20} />
                <span className="text-text truncate">{t.assignee.displayName}</span>
              </>
            ) : (
              <span className="text-text-faint">—</span>
            )}
          </div>

          {/* Reporter row — ticket creator; '—' when null (Plan 03 contract) */}
          <div className="flex items-center gap-2 text-sm">
            <span className="text-xs text-text-muted w-16 shrink-0">Reporter</span>
            {t.reporter ? (
              <>
                <Avatar name={t.reporter.displayName} email={t.reporter.email} size={20} />
                <span className="text-text truncate">{t.reporter.displayName}</span>
              </>
            ) : (
              <span className="text-text-faint">—</span>
            )}
          </div>

          {/* WatcherStack — role-tagged + deduped list (D-W-04) */}
          <div className="space-y-1">
            <span className="text-xs text-text-muted block">Watchers</span>
            <WatcherStack watchers={watcherList} />
          </div>

          {/* Watch/Watching toggle button (D-W-03) */}
          <button
            type="button"
            onClick={() => watch.mutate(!isWatching)}
            disabled={watch.isPending}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border-subtle bg-surface-2 px-3 py-1.5 text-xs font-medium text-text-muted hover:border-border hover:text-text focus:outline-none focus-visible:ring-2 focus-visible:ring-violet disabled:cursor-not-allowed disabled:opacity-40"
            aria-label={isWatching ? 'Watching — click to unwatch' : 'Watch this ticket'}
          >
            {isWatching ? (
              <>
                <EyeOff className="size-3.5" aria-hidden />
                Watching
              </>
            ) : (
              <>
                <Eye className="size-3.5" aria-hidden />
                Watch
              </>
            )}
          </button>
        </div>

        {/* Asset cross-link card (TicketAssetCard) */}
        <TicketAssetCard
          assetId={t.asset?.assetId ?? null}
          hostname={t.asset?.hostname ?? null}
          osName={t.asset?.osName ?? null}
          riskScore={t.asset?.riskScore ?? null}
        />
      </aside>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page export: ErrorBoundary > Suspense > TicketDetailInner (mirrors assets/[id])
// ---------------------------------------------------------------------------
export default function TicketDetailPage() {
  return (
    <ErrorBoundary
      fallback={(err, reset) => (
        <PartialFailureBanner
          // WR-10: full err.message — no .slice.
          errors={[{ code: 'crash', requestId: err.message || 'unknown' }]}
          onRetry={reset}
        />
      )}
    >
      <Suspense fallback={<SkeletonTable columns={SKELETON_COLUMNS} rows={8} />}>
        <TicketDetailInner />
      </Suspense>
    </ErrorBoundary>
  );
}
