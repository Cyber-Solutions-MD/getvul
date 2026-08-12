'use client';
/**
 * /dashboard/cspm — UX-06-01
 *
 * CSPM page rewrite. Replaces v1 tab-based layout (Findings/Compliance/Resources/Trends)
 * with a single chip-bar filtered finding list + DrillPanel + compliance frameworks rail.
 *
 * Deferred: Trends chart (D-CSPM-04 / UX-D-05).
 * Resources tab removed — no separate endpoint in v2 design.
 *
 * T-14-10: ChipBar allowLists clamp reflected URL values; no arbitrary input reaches backend.
 * T-14-11: POST /cspm/bulk-status requires Analyst+ server-side; 403 surfaces as error toast.
 * T-14-12: ConnectorMark literal lookup in FindingCard (no var injection).
 *
 * Plan 14-03.
 */
import { Suspense, useCallback, useMemo } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { Lightbulb } from 'lucide-react';
import { ChipBar, type ChipAxis } from '@/components/ui/ChipBar';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { DrillPanel } from '@/components/vulnerabilities/drill-panel';
import { DrillPanelMobile } from '@/components/vulnerabilities/drill-panel-mobile';
import { FindingCard } from '@/components/cspm/finding-card';
import { FindingDrillContent } from '@/components/cspm/finding-drill-content';
import { ComplianceFrameworkStrip } from '@/components/cspm/compliance-framework-strip';
import { CspmBulkBar } from '@/components/cspm/cspm-bulk-bar';
import { CSPM_MICROCOPY, SEVERITY_GLYPH, SEVERITY_CLASS } from '@/components/cspm/microcopy';
import { SkeletonTable, EmptyState, PartialFailureBanner, type SkeletonColumn } from '@/components/states';
import { useUrlState } from '@/hooks/use-url-state';
import { useUrlStateList } from '@/hooks/use-url-state-list';
import {
  useCspmFindings,
  useCspmStats,
  useComplianceFrameworks,
  useBulkCspmStatus,
  type CspmFilters,
} from '@/lib/queries/use-cspm-findings';
import { queryKeys } from '@/lib/queries/keys';
import { cn } from '@/lib/utils';
import React, { useState } from 'react';

// ── Allow-lists (T-14-10 / T-12-05 XSS guard) ────────────────────────────────
const SEVERITIES = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'] as const;
const STATUSES = ['OPEN', 'IN_PROGRESS', 'REMEDIATED', 'SUPPRESSED', 'FALSE_POSITIVE'] as const;
const SOURCES = ['CROWDSTRIKE', 'WIZ', 'DEFENDER', 'QUALYS', 'RAPID7', 'NESSUS'] as const;
const CLOUD_PROVIDERS = ['ALL', 'AWS', 'AZURE', 'GCP'] as const;
// Phase 35 SRC-02/05: OR (any selected tool, default) vs AND (true
// multi-tool corroboration via the backend's read-time
// GROUP BY(tenant_id, rule_id, resource_id) — Plan 04).
const SOURCE_MODES = ['or', 'and'] as const;

type Severity = typeof SEVERITIES[number];
type Status = typeof STATUSES[number];
type Source = typeof SOURCES[number];

// ── Skeleton columns (mirrors finding card shape) ─────────────────────────────
const SKELETON_COLUMNS: SkeletonColumn[] = [
  { kind: 'badge', width: 14 },
  { kind: 'mono', width: 100 },
  { kind: 'text', width: 220 },
  { kind: 'mono', width: 160 },
  { kind: 'pill', width: 80 },
];

// ── CTA styles ────────────────────────────────────────────────────────────────
const CTA_PRIMARY = 'rounded-md bg-gradient-sunset px-4 py-2 text-sm font-medium text-text-inverse shadow-glow-cta focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet';
const CTA_SECONDARY = 'rounded-md border border-border-subtle bg-surface-2 px-4 py-2 text-sm text-text hover:bg-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet';

// ── ChipBar axes ─────────────────────────────────────────────────────────────
const CSPM_AXES: ChipAxis[] = [
  {
    key: 'severity',
    label: 'Severity',
    allowList: SEVERITIES,
    chips: SEVERITIES.map((s) => ({
      value: s,
      label: s.charAt(0) + s.slice(1).toLowerCase(),
      glyph: SEVERITY_GLYPH[s],
      glyphClassName: SEVERITY_CLASS[s],
    })),
  },
  {
    key: 'status',
    label: 'Status',
    allowList: STATUSES,
    chips: [
      { value: 'OPEN', label: 'Open' },
      { value: 'IN_PROGRESS', label: 'In progress' },
      { value: 'REMEDIATED', label: 'Remediated' },
      { value: 'SUPPRESSED', label: 'Suppressed' },
    ],
  },
  {
    key: 'source',
    label: 'Source',
    allowList: SOURCES,
    chips: SOURCES.map((s) => ({ value: s, label: s })),
  },
];

// ── WatchKeys for PartialFailureBanner ────────────────────────────────────────
const WATCH_KEYS = [queryKeys.cspm.all] as const;

// ── Page component ────────────────────────────────────────────────────────────

function CspmPageInner() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  // URL filter state (T-14-10: clamped by useUrlStateList allowList)
  const [severity, setSeverity] = useUrlStateList<Severity>('severity', SEVERITIES, []);
  const [status, setStatus] = useUrlStateList<Status>('status', STATUSES, []);
  const [source, setSource] = useUrlStateList<Source>('source', SOURCES, []);
  const [cloudProvider, setCloudProvider] = useUrlState<string>('cloud_provider', CLOUD_PROVIDERS as unknown as readonly string[], 'ALL');
  // Phase 35 SRC-02/05 — OR/AND source_mode toggle, sibling to the source
  // axis (mirrors vulnerabilities/chip-bar.tsx's Plan-02 pattern). Disabled
  // below 2 selected sources (Pitfall 1) — the backend documents AND-with-<2
  // as a no-op OR fallback.
  const [sourceMode, setSourceMode] = useUrlState<(typeof SOURCE_MODES)[number]>('source_mode', SOURCE_MODES, 'or');
  const sourceModeDisabled = source.length < 2;
  const sourceModeIsAnd = sourceMode === 'and';

  const search = params?.get('search') ?? '';
  const pageNum = Math.max(1, Number(params?.get('page') ?? '1') || 1);

  // Drill panel state from URL
  const findingId = params?.get('finding') ?? null;

  // Bulk selection state (local — not URL-synced; reset on navigate)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // ── Build filters ──────────────────────────────────────────────────────────
  const filters: CspmFilters = useMemo(() => ({
    severity: severity.length > 0 ? severity : undefined,
    status: status.length > 0 ? status : undefined,
    source: source.length > 0 ? source : undefined,
    source_mode: sourceMode,
    cloud_provider: cloudProvider !== 'ALL' ? cloudProvider : undefined,
    search: search || undefined,
  }), [severity, status, source, sourceMode, cloudProvider, search]);

  // ── Data fetching ──────────────────────────────────────────────────────────
  const findingsQ = useCspmFindings({ filters, page: pageNum });
  const statsQ = useCspmStats();
  const frameworksQ = useComplianceFrameworks();
  const bulkMutation = useBulkCspmStatus();

  // ── Drill panel handlers ───────────────────────────────────────────────────
  const handleOpenFinding = useCallback((id: string) => {
    const sp = new URLSearchParams(params?.toString() ?? '');
    sp.set('finding', id);
    sp.set('open', 'drill');
    const qs = sp.toString();
    router.replace(qs ? `${pathname}?${qs}` : (pathname ?? '/'), { scroll: false });
  }, [router, pathname, params]);

  // ── Bulk selection handlers ────────────────────────────────────────────────
  const handleSelect = useCallback((id: string, selected: boolean) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (selected) next.add(id); else next.delete(id);
      return next;
    });
  }, []);

  const handleBulkAction = useCallback((bulkStatus: 'REMEDIATED' | 'SUPPRESSED' | 'OPEN') => {
    bulkMutation.mutate({ ids: Array.from(selectedIds), status: bulkStatus });
    setSelectedIds(new Set());
  }, [bulkMutation, selectedIds]);

  const handleClearSelection = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  // ── Filter state checks ────────────────────────────────────────────────────
  const hasActiveFilters = severity.length > 0 || status.length > 0 || source.length > 0 || search.length > 0 || cloudProvider !== 'ALL';
  const isEmptyFiltered = !!findingsQ.data && findingsQ.data.items.length === 0 && hasActiveFilters;
  const isEmptyTotal = !!findingsQ.data && findingsQ.data.items.length === 0 && !hasActiveFilters;

  // ── Cloud provider control options (from stats) ────────────────────────────
  const cloudOptions: string[] = useMemo(() => {
    const fromStats = statsQ.data?.by_cloud_provider?.map((c) => c.cloud_provider) ?? [];
    return ['ALL', ...fromStats.filter((cp) => (CLOUD_PROVIDERS as readonly string[]).includes(cp))];
  }, [statsQ.data]);

  return (
    <>
      <h1 className="sr-only">{CSPM_MICROCOPY.page.h1}</h1>
      <div className="space-y-4">
        {/* Error banner */}
        {findingsQ.isError && (
          <PartialFailureBanner
            errors={[{ code: 'ERR', requestId: '' }]}
            onRetry={() => findingsQ.refetch()}
          />
        )}

        {/* Chip-bar (hidden in empty-filtered branch) */}
        {!isEmptyFiltered && (
          <ChipBar
            axes={CSPM_AXES}
            searchPlaceholder="Search rule, resource…"
            searchAriaLabel="Search CSPM findings"
          />
        )}

        {/* Phase 35 SRC-02/05 — OR/AND source_mode toggle, sibling to the
            source axis (ChipAxis has no mode field). Disabled below 2
            selected sources — a no-op AND is worse UX than an inert
            control. Mirrors chip-bar.tsx's (Plan 02) toggle shape + copy
            verbatim. */}
        {!isEmptyFiltered && (
          <div className="flex items-center gap-2 px-1">
            <span className="text-xs uppercase tracking-wide text-text-muted">
              {CSPM_MICROCOPY.chips.sourceModeLabel}
            </span>
            <button
              type="button"
              onClick={() => setSourceMode(sourceModeIsAnd ? 'or' : 'and')}
              disabled={sourceModeDisabled}
              aria-pressed={sourceModeIsAnd}
              title={sourceModeDisabled ? CSPM_MICROCOPY.chips.sourceModeDisabledHint : undefined}
              data-source-mode-toggle
              className={cn(
                'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition-colors',
                'focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet',
                'disabled:cursor-not-allowed disabled:opacity-50',
                sourceModeIsAnd
                  ? 'border-border bg-surface-2 text-text'
                  : 'border-border-subtle bg-surface text-text-muted hover:bg-surface-2 hover:text-text',
              )}
            >
              {sourceModeIsAnd ? CSPM_MICROCOPY.chips.sourceModeAll : CSPM_MICROCOPY.chips.sourceModeAny}
            </button>
          </div>
        )}

        {/* Cloud segmented control (D-CSPM-02) */}
        {!isEmptyFiltered && cloudOptions.length > 1 && (
          <div className="flex items-center gap-1.5" role="group" aria-label="Cloud provider filter">
            {cloudOptions.map((cp) => (
              <button
                key={cp}
                type="button"
                onClick={() => setCloudProvider(cp)}
                className={cn(
                  'rounded-md border px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet',
                  cloudProvider === cp
                    ? 'border-violet bg-violet/10 text-[var(--color-violet-on-soft)]'
                    : 'border-border-subtle bg-surface text-text-muted hover:bg-surface-2 hover:text-text',
                )}
              >
                {cp}
              </button>
            ))}
          </div>
        )}

        {/* Compliance frameworks strip */}
        {frameworksQ.data && frameworksQ.data.length > 0 && (
          <ComplianceFrameworkStrip frameworks={frameworksQ.data} />
        )}

        {/* Main content area */}
        {findingsQ.isPending ? (
          <SkeletonTable rows={8} columns={SKELETON_COLUMNS} />
        ) : isEmptyFiltered ? (
          /* Filtered to zero — 3-tier CTAs + lightbulb */
          <EmptyState>
            <EmptyState.Title>{CSPM_MICROCOPY.emptyState.heading}</EmptyState.Title>
            <EmptyState.Body>{CSPM_MICROCOPY.emptyState.body}</EmptyState.Body>
            <EmptyState.Actions>
              <button
                type="button"
                onClick={() => { setSeverity([]); setStatus([]); setSource([]); setCloudProvider('ALL'); }}
                className={CTA_PRIMARY}
              >
                {CSPM_MICROCOPY.emptyState.clearAll}
              </button>
              <button
                type="button"
                onClick={() => setSeverity([])}
                className={CTA_SECONDARY}
              >
                {CSPM_MICROCOPY.emptyState.broadenSeverity}
              </button>
              <button
                type="button"
                onClick={() => setSource([])}
                className={CTA_SECONDARY}
              >
                {CSPM_MICROCOPY.emptyState.broadenSource}
              </button>
            </EmptyState.Actions>
            <EmptyState.Suggestion>
              <Lightbulb size={16} aria-hidden="true" className="mt-0.5 shrink-0" />
              <span>{CSPM_MICROCOPY.emptyState.lightbulb}</span>
            </EmptyState.Suggestion>
          </EmptyState>
        ) : isEmptyTotal ? (
          /* No data at all */
          <EmptyState>
            <EmptyState.Title>No CSPM findings</EmptyState.Title>
            <EmptyState.Body>
              Connect a cloud scanner to see findings here.
            </EmptyState.Body>
          </EmptyState>
        ) : (
          /* Finding list */
          <div className="space-y-2">
            {(findingsQ.data?.items ?? []).map((finding) => (
              <FindingCard
                key={finding.id}
                finding={finding}
                selected={selectedIds.has(finding.id)}
                onSelect={handleSelect}
                onOpen={handleOpenFinding}
              />
            ))}
          </div>
        )}

        {/* DrillPanel — idKey='finding', opens at ?finding=<id>&open=drill.
            Desktop (>=900px) is the 420px right aside; mobile (<900px) is the vaul
            bottom sheet — pairs with DrillPanelMobile (UX-06-01/UX-07-02), matching
            the vuln/ticket/asset drill surfaces. */}
        <DrillPanel
          id={findingId}
          idKey="finding"
          ariaLabel="Finding detail"
          renderContent={({ id, onClose }) => (
            <FindingDrillContent findingId={id} onClose={onClose} />
          )}
        />
        <DrillPanelMobile
          id={findingId}
          idKey="finding"
          ariaLabel="Finding detail"
          renderContent={({ id, onClose }) => (
            <FindingDrillContent findingId={id} onClose={onClose} />
          )}
        />

        {/* Bulk action bar */}
        <CspmBulkBar
          selectedCount={selectedIds.size}
          onBulkAction={handleBulkAction}
          onClearSelection={handleClearSelection}
          isPending={bulkMutation.isPending}
        />
      </div>
    </>
  );
}

export default function CspmPage() {
  useDocumentTitle('CSPM findings');
  return (
    <Suspense>
      <CspmPageInner />
    </Suspense>
  );
}
