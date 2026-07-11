'use client';
/**
 * /tickets/rules — UX-05-01 sunset rewrite of the v1 ?tab=rules surface (D-S-01).
 *
 * Composes:
 *   - ChipBar (Status axis: enabled/disabled) — URL-synced via useUrlStateList per axis (T-12-05)
 *   - SkeletonTable (loading) — state-patterns.md D-S-01; mutually exclusive (WR-13)
 *   - EmptyState (no rules) — peer voice per copy-voice.md
 *   - PartialFailureBanner (error) — full err.message, no slice (WR-10/15)
 *   - RulesList (rows) — name + enabled pill + conditions/action summary
 *
 * No v1 carryover: no v1 panel imports, no query param tab, no inline hex.
 * No inline hex: sunset tokens only (CSS variables).
 */
import { Suspense, useMemo, type ReactNode } from 'react';
import { useSearchParams } from 'next/navigation';
import { ChipBar, type ChipAxis } from '@/components/ui/ChipBar';
import {
  SkeletonTable,
  EmptyState,
  PartialFailureBanner,
  type SkeletonColumn,
} from '@/components/states';
import { ErrorBoundary } from '@/components/ui/error-boundary';
import { useUrlStateList } from '@/hooks/use-url-state-list';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { useTicketRules, type TicketRule } from '@/lib/queries/use-ticket-rules';
import { ApiError } from '@/lib/api';
import { cn } from '@/lib/utils';

// XSS allow-list for status chip (T-12-05 / T-13-31).
// Values match is_enabled boolean → 'enabled' | 'disabled' strings.
const STATUS_ALLOW_LIST = ['enabled', 'disabled'] as const;

// Chip axes — one Status axis with hardcoded allowList (T-12-05).
const RULES_AXES: ChipAxis[] = [
  {
    key: 'status',
    label: 'Status',
    allowList: STATUS_ALLOW_LIST,
    chips: [
      { value: 'enabled', label: 'Enabled' },
      { value: 'disabled', label: 'Disabled' },
    ],
  },
];

// 4-column skeleton: name, status, provider/mode, schedule.
const SKELETON_COLUMNS: SkeletonColumn[] = [
  { kind: 'text', width: 240 },  // name
  { kind: 'badge', width: 80 },  // status
  { kind: 'text', width: 160 },  // provider / mode
  { kind: 'mono', width: 100 },  // schedule
];

// Map an unknown error to the banner's {code, requestId, message} row. api.ts
// throws ApiError carrying the HTTP status + Phase-07 X-Request-ID; surface
// those in their proper slots (previously code was hardcoded and err.message
// was crammed into requestId). WR-10: pass full err.message — the banner
// truncates visually.
function toErrorRow(err: unknown, fallbackCode: number | string) {
  if (err instanceof ApiError) {
    return { code: err.code, requestId: err.requestId, message: err.message };
  }
  return {
    code: fallbackCode,
    requestId: 'unknown',
    message: err instanceof Error ? err.message : undefined,
  };
}

function pageErrorFallback(err: Error, reset: () => void): ReactNode {
  return (
    <div className="space-y-4 p-6">
      <h1 className="sr-only">Automation rules</h1>
      <PartialFailureBanner errors={[toErrorRow(err, 'crash')]} onRetry={reset} />
    </div>
  );
}

// Rule row: name + enabled pill + summary. Rendered as text nodes (T-13-32).
function RuleRow({ rule }: { rule: TicketRule }) {
  const enabledPill = rule.is_enabled ? (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium',
        'border-severity-low/40 bg-severity-low/10 text-severity-low',
      )}
    >
      Enabled
    </span>
  ) : (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium',
        'border-border-subtle bg-surface-2 text-text-faint',
      )}
    >
      Disabled
    </span>
  );

  // Action summary: provider + mode
  const action = rule.action as Record<string, unknown>;
  const provider = typeof action.provider === 'string' ? action.provider : '—';
  const mode = typeof action.ticket_mode === 'string' ? action.ticket_mode.replace(/_/g, ' ') : '—';

  // Schedule summary: minutes → human-readable
  const scheduleLabel =
    rule.schedule_minutes >= 1440
      ? `Every ${rule.schedule_minutes / 1440}d`
      : `Every ${rule.schedule_minutes}min`;

  return (
    <tr className="border-b border-border-subtle hover:bg-surface/60 transition-colors">
      <td className="px-4 py-3 text-sm text-text font-medium">{rule.name}</td>
      <td className="px-4 py-3">{enabledPill}</td>
      <td className="px-4 py-3 text-sm text-text-muted">
        {provider} · {mode}
      </td>
      <td className="px-4 py-3 text-sm font-mono text-text-faint">{scheduleLabel}</td>
    </tr>
  );
}

function RulesList({ rules }: { rules: TicketRule[] }) {
  return (
    <table className="w-full">
      <thead>
        <tr className="border-b border-border text-left">
          <th className="px-4 py-2 text-xs font-medium uppercase tracking-wide text-text-muted">Name</th>
          <th className="px-4 py-2 text-xs font-medium uppercase tracking-wide text-text-muted">Status</th>
          <th className="px-4 py-2 text-xs font-medium uppercase tracking-wide text-text-muted">Provider / Mode</th>
          <th className="px-4 py-2 text-xs font-medium uppercase tracking-wide text-text-muted">Schedule</th>
        </tr>
      </thead>
      <tbody>
        {rules.map((rule) => (
          <RuleRow key={rule.id} rule={rule} />
        ))}
      </tbody>
    </table>
  );
}

function RulesPageInner() {
  const params = useSearchParams();
  useDocumentTitle('Automation rules');

  // Status chip axis — URL-synced, clamped by allowList (T-13-31 / T-12-05).
  const [statusFilter] = useUrlStateList<string>('status', STATUS_ALLOW_LIST, []);

  const q = useTicketRules();

  // Client-side filter: if status chips are active, filter rules by is_enabled.
  // No additional fetch — filtering on the already-loaded list.
  const filteredRules = useMemo(() => {
    const rules = q.data ?? [];
    if (statusFilter.length === 0) return rules;
    return rules.filter((r) => {
      if (statusFilter.includes('enabled') && r.is_enabled) return true;
      if (statusFilter.includes('disabled') && !r.is_enabled) return true;
      return false;
    });
  }, [q.data, statusFilter]);

  const search = params?.get('search') ?? '';

  // Search filter: match rule name case-insensitively.
  const visibleRules = useMemo(() => {
    if (!search) return filteredRules;
    const lower = search.toLowerCase();
    return filteredRules.filter((r) => r.name.toLowerCase().includes(lower));
  }, [filteredRules, search]);

  return (
    <div className="space-y-4 p-6">
      <header className="space-y-1">
        <div className="text-xs uppercase tracking-wide text-text-muted">
          Tickets · Automation
        </div>
        <h1 className="text-2xl font-semibold text-text">Automation rules</h1>
      </header>

      <ChipBar
        axes={RULES_AXES}
        searchPlaceholder="Search rules…"
        searchAriaLabel="Search rules"
      />

      {/* WR-13: mutually exclusive state branches. Error first, then loading, then
          empty, then list. If we check items.length before error, an error with
          empty data would show contradictory "No rules" + alert states. */}
      {q.error ? (
        <PartialFailureBanner
          errors={[toErrorRow(q.error, 'http_error')]}
          onRetry={() => q.refetch()}
        />
      ) : q.isLoading ? (
        <SkeletonTable columns={SKELETON_COLUMNS} rows={6} />
      ) : (q.data?.length ?? 0) === 0 ? (
        <EmptyState>
          <EmptyState.Title>No automation rules yet</EmptyState.Title>
          <EmptyState.Body>
            Create a rule to auto-route new findings to your ticketing provider — no manual triage required.
          </EmptyState.Body>
        </EmptyState>
      ) : visibleRules.length === 0 ? (
        // Filters active but no matching rules
        <EmptyState>
          <EmptyState.Title>No rules match these filters</EmptyState.Title>
          <EmptyState.Body>Try adjusting the status filter or search query.</EmptyState.Body>
        </EmptyState>
      ) : (
        <RulesList rules={visibleRules} />
      )}
    </div>
  );
}

const PAGE_FALLBACK = (
  <div className="space-y-4 p-6">
    <h1 className="sr-only">Automation rules</h1>
    <SkeletonTable columns={SKELETON_COLUMNS} rows={6} />
  </div>
);

export default function RulesPage() {
  return (
    <ErrorBoundary fallback={pageErrorFallback} boundaryName="RulesPage">
      <Suspense fallback={PAGE_FALLBACK}>
        <RulesPageInner />
      </Suspense>
    </ErrorBoundary>
  );
}
