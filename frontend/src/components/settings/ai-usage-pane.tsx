'use client';
/**
 * AiUsagePane — AIE-04 admin-only "AI usage & settings" pane (28-UI-SPEC.md).
 *
 * One admin home for AI usage/cost/settings: month-to-date spend vs budget
 * (with a restyled shadcn `progress` meter), a 6-row per-capability usage
 * breakdown, the derived breaker status (amber banner + pill), and a
 * read-only key & model summary that LINKS OUT to the existing Connectors
 * wizard (D-05 — this pane does NOT rebuild key/model/budget edit UI).
 *
 * Data source: a single `useAiUsage()` GET, locked response shape from
 * Plan 03's `backend/app/api/v1/ai/usage.py`. No independent client-side
 * derivation of `breaker_tripped` — the backend's own comparison is trusted
 * verbatim (D-09).
 *
 * RBAC (T-14-04/T-14-16 precedent, zero new gating code): 'ai' is
 * ADMIN_ONLY in settings-sidebar-shell.tsx (UX-layer hide only). The
 * backend route is require_admin-gated — a non-admin who hand-crafts
 * ?category=ai still gets a 403 from useAiUsage(), rendered via the same
 * PartialFailureBanner every sibling admin pane uses.
 *
 * State patterns (mandatory, state-patterns.md):
 *   isPending → lightweight pulse (single admin-gated query, <300ms
 *     expected — NOT a heavy SkeletonTable, mirrors AiExplanationSection's
 *     own prereqsPending treatment).
 *   isError   → PartialFailureBanner (verbatim, no new error copy).
 *   !configured → "AI isn't set up yet" card (whole-pane replacement).
 *   configured, zero usage → the 4 cards still render with zero-value
 *     shapes + a "No AI usage yet" notice (never replace the pane).
 *
 * data-pane="ai" for test hooks (mirrors audit-log-pane.tsx's data-pane
 * convention).
 *
 * Phase 28, Plan 04.
 */
import Link from 'next/link';
import { AlertTriangle, Sparkles } from 'lucide-react';
import { useAiUsage, type AiUsageCapabilityRow, type AiUsageResult } from '@/lib/queries/use-ai-usage';
import { queryKeys } from '@/lib/queries/keys';
import { PartialFailureBanner } from '@/components/states';
import { Stat } from '@/components/ui/stat';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';

// ── Formatting helpers ───────────────────────────────────────────────────────

function formatUsd(n: number): string {
  return `$${n.toFixed(2)}`;
}

function formatTokens(n: number): string {
  return n.toLocaleString();
}

// Model is shown as the connector wizard's own short enum label, never the
// raw model-id string (28-UI-SPEC.md Key & model card contract). Matched by
// family-name substring rather than the exact id so this never has to
// embed the raw id literal here, and stays correct across any future
// dated-suffix id change. Falls back to a generic label for anything
// unrecognized — this pane must never render a raw model id verbatim.
function modelDisplayLabel(model: string): string {
  const m = model.toLowerCase();
  if (m.includes('opus')) return 'Opus 5';
  if (m.includes('haiku')) return 'Haiku';
  if (m.includes('sonnet')) return 'Sonnet 5';
  return 'Claude';
}

// ── Fixed 6-row capability table shape (28-UI-SPEC Meter/Table Contract) ────
// Hardcoded here — NOT derived from the API array's length — so exactly 6
// rows always render regardless of what the backend returns, and a
// stray/fabricated 7th row (e.g. a future "ticket-draft" resource_type)
// can never surface in this table. "ticket-draft" calls are NOT a separate
// attributable capability today — they fold into rows 1 and 4 below
// (research finding, not an omission).
const CAPABILITY_ROWS: ReadonlyArray<{
  resourceType: string;
  isBatch: boolean | null;
  label: string;
}> = [
  { resourceType: 'vuln', isBatch: null, label: 'Explain — vulnerability' },
  { resourceType: 'host', isBatch: null, label: 'Explain — host posture' },
  { resourceType: 'remediation', isBatch: null, label: 'Explain — remediation impact' },
  { resourceType: 'remediation-guidance', isBatch: null, label: 'Remediation guidance' },
  { resourceType: 'prioritization', isBatch: false, label: 'Prioritization — on demand' },
  { resourceType: 'prioritization', isBatch: true, label: 'Prioritization — batch' },
];

function findRow(
  rows: AiUsageCapabilityRow[],
  resourceType: string,
  isBatch: boolean | null,
): AiUsageCapabilityRow | undefined {
  return rows.find((r) => r.resource_type === resourceType && r.is_batch === isBatch);
}

// ── 3-state status pill (RECREATED recipe — SyncStatusPill itself is ───────
// connector-sync-specific; this is a new instance of the same visual
// recipe, per 28-UI-SPEC.md's Color section, not an import).
type PillState = 'active' | 'paused' | 'not_configured';

const STATUS_PILL: Record<PillState, { label: string; className: string }> = {
  active: {
    label: 'Active',
    className: 'border-severity-low/40 bg-severity-low/10 text-severity-low',
  },
  paused: {
    label: 'Paused — budget exceeded',
    className: 'border-amber/40 bg-amber/10 text-[var(--color-amber-on-soft)]',
  },
  not_configured: {
    label: 'Not configured',
    className: 'border-border-subtle bg-surface-2 text-text-faint',
  },
};

function pillStateFor(data: AiUsageResult): PillState {
  if (!data.configured) return 'not_configured';
  if (data.breaker_tripped) return 'paused';
  return 'active';
}

// ── Degraded/neutral card chrome (RECREATED — the original DegradedCard in ──
// ai-explanation-section.tsx is module-private and cannot be imported).
function AiStateCard({
  variant,
  heading,
  body,
  action,
}: {
  variant: 'neutral' | 'amber';
  heading: string;
  body: string;
  action?: { label: string; href: string };
}) {
  const chipClass =
    variant === 'amber'
      ? 'bg-amber-soft text-[var(--color-amber-on-soft)]'
      : 'bg-violet-soft text-[var(--color-violet-on-soft)]';
  return (
    <div role="status" className="rounded-lg border border-border-subtle bg-surface-2 p-5">
      <div className={cn('mb-3 flex h-8 w-8 items-center justify-center rounded-full', chipClass)}>
        {variant === 'amber' ? (
          <AlertTriangle className="h-4 w-4" aria-hidden="true" />
        ) : (
          <Sparkles className="h-4 w-4" aria-hidden="true" />
        )}
      </div>
      <p className="text-sm font-medium text-text">{heading}</p>
      <p className="mt-1 text-sm text-text-muted">{body}</p>
      {action && (
        <Link
          href={action.href}
          className="mt-4 inline-flex w-fit items-center justify-center gap-1.5 rounded-md border border-border bg-surface-2 px-4 py-2 text-sm font-medium text-text hover:bg-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
        >
          {action.label}
        </Link>
      )}
    </div>
  );
}

// Budget meter SLA 3-tier fill (28-UI-SPEC Meter Contract): <75% success,
// 75-99% amber, >=100% danger — a reuse of the SLA color convention, not a
// new threshold scheme.
function meterIndicatorClass(percentUsed: number): string {
  if (percentUsed >= 100) return 'bg-danger';
  if (percentUsed >= 75) return 'bg-amber';
  return 'bg-success';
}

const H2_CLASS = 'text-base font-semibold text-text';
const CARD_CLASS = 'rounded-lg border border-border-subtle bg-surface p-5';
const SECONDARY_LINK_CLASS =
  'mt-4 inline-flex w-fit items-center justify-center gap-1.5 rounded-md border border-border bg-surface-2 px-4 py-2 text-sm font-medium text-text hover:bg-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet';

export function AiUsagePane() {
  const { data, isPending, isError, refetch } = useAiUsage();

  // Loading: single admin-gated query, <300ms expected — a lightweight
  // pulse placeholder, never a heavy SkeletonTable (state-patterns.md).
  if (isPending) {
    return (
      <div data-pane="ai" className="p-6 space-y-6">
        <div aria-hidden="true" className="space-y-4">
          <div className="h-24 animate-pulse rounded-lg bg-surface-2" />
          <div className="h-40 animate-pulse rounded-lg bg-surface-2" />
          <div className="h-32 animate-pulse rounded-lg bg-surface-2" />
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div data-pane="ai" className="p-6 space-y-6">
        <PartialFailureBanner watchKeys={[queryKeys.ai.usage()]} onRetry={refetch} />
      </div>
    );
  }

  if (!data) {
    // Defensive — isPending/isError above already cover every other
    // TanStack Query state; this only satisfies strict-null-checks.
    return null;
  }

  // Empty state 1 (no key configured): the WHOLE pane replaces with a
  // single card — role is always Admin/Owner here (pane is admin-gated),
  // so the CTA branch always renders (Copywriting Contract).
  if (!data.configured) {
    return (
      <div data-pane="ai" className="p-6 space-y-6">
        <AiStateCard
          variant="neutral"
          heading="AI isn't set up yet"
          body="Configure your Anthropic key to turn on AI-assisted triage. Usage and cost will show up here once it's on."
          action={{ label: 'Configure AI', href: '/dashboard/connectors' }}
        />
      </div>
    );
  }

  const isZeroUsage = data.capability_breakdown.every((row) => row.calls === 0);
  const totalCalls = data.capability_breakdown.reduce((sum, row) => sum + row.calls, 0);
  const cap = data.monthly_budget_usd;
  const percentUsed = cap !== null ? (cap > 0 ? (data.spent_this_month_usd / cap) * 100 : 100) : 0;
  const meterValue = Math.min(100, Math.max(0, percentUsed));

  return (
    <div data-pane="ai" className="p-6 space-y-6">
      {/* Breaker-tripped banner — the pane's primary visual anchor while
          tripped, rendered ABOVE everything else. */}
      {data.breaker_tripped && (
        <AiStateCard
          variant="amber"
          heading="AI paused — budget exceeded"
          body="This month's AI budget is used up — every AI surface (explanations, remediation guidance, prioritization, ticket drafting) has degraded to the deterministic risk score only. Raise the cap or wait for next month's reset."
          action={{ label: 'Raise the cap', href: '/dashboard/connectors' }}
        />
      )}

      {/* Empty state 2 (key configured, zero usage): the 4 cards below
          still render with zero-value shapes — this is a supplementary
          notice, never a whole-pane replacement. */}
      {isZeroUsage && (
        <div className="rounded-lg border border-border-subtle bg-surface-2 p-4 text-sm">
          <p className="font-medium text-text">No AI usage yet</p>
          <p className="mt-1 text-text-muted">
            No AI calls have been made this month. Usage and cost will appear here as soon as an analyst runs an
            explanation, remediation guidance, or prioritization.
          </p>
        </div>
      )}

      {/* Status + Budget — one card, two h2-labeled sub-sections. */}
      <section className={CARD_CLASS}>
        <div className="flex items-center justify-between">
          <h2 className={H2_CLASS}>Status</h2>
          <span
            className={cn(
              'inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium',
              STATUS_PILL[pillStateFor(data)].className,
            )}
          >
            <span className="size-1.5 rounded-full bg-current" />
            {STATUS_PILL[pillStateFor(data)].label}
          </span>
        </div>

        <div className="my-4 border-t border-border-subtle" />

        <h2 className={cn(H2_CLASS, 'mb-4')}>Budget</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Stat label="Spent this month" value={formatUsd(data.spent_this_month_usd)} delta={0} />
          <Stat label="AI calls this month" value={totalCalls.toLocaleString()} delta={0} />
        </div>

        <div className="mt-4">
          {cap !== null ? (
            <>
              <Progress
                value={meterValue}
                indicatorClassName={meterIndicatorClass(percentUsed)}
                aria-label={`Monthly AI budget used — ${formatUsd(data.spent_this_month_usd)} of ${formatUsd(cap)} (${Math.round(percentUsed)}%)`}
              />
              <p className="mt-2 text-sm text-text-muted">
                {percentUsed >= 100
                  ? `${formatUsd(data.spent_this_month_usd)} of ${formatUsd(cap)} used this month — cap reached`
                  : `${formatUsd(data.spent_this_month_usd)} of ${formatUsd(cap)} used this month (${Math.round(percentUsed)}%)`}
              </p>
            </>
          ) : (
            <p className="text-sm text-text-muted">No monthly cap set — spend is unlimited for this tenant.</p>
          )}
        </div>
      </section>

      {/* Usage by capability — verbatim audit-log-pane table chrome. */}
      <section className={CARD_CLASS}>
        <h2 className={cn(H2_CLASS, 'mb-4')}>Usage by capability</h2>
        <div className="overflow-x-auto rounded-lg border border-border-subtle">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border-subtle bg-surface">
              <tr>
                <th className="px-4 py-3 text-xs font-medium uppercase tracking-wide text-text-faint">Capability</th>
                <th className="px-4 py-3 text-xs font-medium uppercase tracking-wide text-text-faint">Calls</th>
                <th className="px-4 py-3 text-xs font-medium uppercase tracking-wide text-text-faint">Cost</th>
                <th className="px-4 py-3 text-xs font-medium uppercase tracking-wide text-text-faint">Tokens</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {CAPABILITY_ROWS.map(({ resourceType, isBatch, label }) => {
                const row = findRow(data.capability_breakdown, resourceType, isBatch);
                return (
                  <tr
                    key={`${resourceType}-${String(isBatch)}`}
                    className="bg-surface hover:bg-surface-2 transition-colors"
                  >
                    <td className="px-4 py-2 text-text">{label}</td>
                    <td className="px-4 py-2 font-mono text-text-muted">{row?.calls ?? 0}</td>
                    <td className="px-4 py-2 font-mono text-text-muted">{formatUsd(row?.cost_usd ?? 0)}</td>
                    <td className="px-4 py-2 font-mono text-text-muted">{formatTokens(row?.tokens ?? 0)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {data.degraded_calls_count > 0 && (
          <p className="mt-3 text-sm text-text-muted">
            {data.degraded_calls_count} calls degraded this month (busy, insufficient evidence, or retried) — see the
            audit log for detail.
          </p>
        )}
      </section>

      {/* Key & model — read-only summary, links out to Connectors (D-05):
          this pane does NOT rebuild key/model/budget edit UI. */}
      <section className={CARD_CLASS}>
        <h2 className={cn(H2_CLASS, 'mb-4')}>Key & model</h2>
        <dl className="space-y-3">
          <div>
            <dt className="text-xs uppercase tracking-wide text-text-faint">Model</dt>
            <dd className="mt-1 font-mono text-sm text-text">{modelDisplayLabel(data.model)}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-text-faint">Monthly budget</dt>
            <dd className="mt-1 font-mono text-sm text-text">{cap !== null ? formatUsd(cap) : 'No cap set'}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-text-faint">Connector</dt>
            <dd className="mt-1 text-sm text-text">{data.configured ? 'Enabled' : 'Disabled'}</dd>
          </div>
        </dl>
        <Link href="/dashboard/connectors" className={SECONDARY_LINK_CLASS}>
          Manage in Connectors
        </Link>
      </section>
    </div>
  );
}
