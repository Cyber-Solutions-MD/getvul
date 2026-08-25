'use client';
/**
 * FrameworkPostureStrip — RPT-02 leadership + compliance-lens widget (Phase
 * 43 Plan 04). One pill per framework (SOC 2 / ISO 27001 / PCI DSS / NIST
 * CSF) aggregating pass/partial/fail/not-measured counts from
 * `useComplianceOverview()` (Plan 01). Each pill deep-links to
 * `/dashboard/compliance?framework=<fw>`.
 *
 * Two variants (43-UI-SPEC.md RPT-02 Phase-Specific Contract), controlled
 * by `variant`:
 *   - `compact` (default) — Leadership-lens item 5: one small pill per
 *     framework, aggregate counts only.
 *   - `hero` — Compliance-lens item 1: the SAME aggregate pills, rendered
 *     larger, PLUS a first-2-controls-per-framework preview grid (the
 *     "hero-sized... full framework-by-framework control grid preview").
 *
 * Analog: `coverage/coverage-connector-card.tsx`'s per-item pill/card strip
 * pattern. Four-state palette per 43-UI-SPEC.md Color: pass=success,
 * partial=warning, fail=danger, not_measured=text-faint on surface-2
 * (dashed border) — never a fabricated status for absent data.
 */
import Link from 'next/link';
import { cn } from '@/lib/utils';
import type { ControlStatus } from '@/lib/queries/use-compliance';

export type FrameworkPostureStripProps = {
  controls: ControlStatus[];
  variant?: 'compact' | 'hero';
  className?: string;
};

const FRAMEWORK_ORDER = ['soc2', 'iso27001', 'pci_dss', 'nist_csf'] as const;

const FRAMEWORK_LABEL: Record<string, string> = {
  soc2: 'SOC 2',
  iso27001: 'ISO 27001',
  pci_dss: 'PCI DSS',
  nist_csf: 'NIST CSF',
};

type StatusCounts = { pass: number; partial: number; fail: number; not_measured: number };

function countByStatus(controls: ControlStatus[]): StatusCounts {
  const counts: StatusCounts = { pass: 0, partial: 0, fail: 0, not_measured: 0 };
  for (const c of controls) counts[c.status] += 1;
  return counts;
}

// Aggregate "headline" status for the pill dot — worst-case-first so a
// single failing control is never hidden behind a majority of passes.
function aggregateStatus(counts: StatusCounts): keyof StatusCounts {
  if (counts.fail > 0) return 'fail';
  if (counts.partial > 0) return 'partial';
  if (counts.pass > 0) return 'pass';
  return 'not_measured';
}

const STATUS_DOT_CLASS: Record<keyof StatusCounts, string> = {
  pass: 'bg-success',
  partial: 'bg-warning',
  fail: 'bg-danger',
  not_measured: 'bg-text-faint',
};

const STATUS_PILL_CLASS: Record<keyof StatusCounts, string> = {
  pass: 'border-success/40 bg-success/10 text-success',
  partial: 'border-warning/40 bg-warning/10 text-warning',
  fail: 'border-danger/40 bg-danger/10 text-danger',
  not_measured: 'border-dashed border-border bg-surface-2 text-text-faint',
};

function FrameworkPill({
  framework,
  counts,
  hero,
}: {
  framework: string;
  counts: StatusCounts;
  hero: boolean;
}) {
  const status = aggregateStatus(counts);
  const total = counts.pass + counts.partial + counts.fail + counts.not_measured;
  return (
    <Link
      href={`/dashboard/compliance?framework=${framework}`}
      data-testid={`framework-pill-${framework}`}
      className={cn(
        'inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors hover:opacity-90',
        hero && 'px-4 py-2 text-sm',
        STATUS_PILL_CLASS[status],
      )}
    >
      <span className={cn('h-2 w-2 rounded-full', STATUS_DOT_CLASS[status])} aria-hidden="true" />
      <span className="font-semibold">{FRAMEWORK_LABEL[framework] ?? framework}</span>
      <span className="font-mono text-text-muted">
        {counts.pass}/{total}
      </span>
    </Link>
  );
}

export function FrameworkPostureStrip({ controls, variant = 'compact', className }: FrameworkPostureStripProps) {
  const byFramework = new Map<string, ControlStatus[]>();
  for (const c of controls) {
    const existing = byFramework.get(c.framework);
    if (existing) existing.push(c);
    else byFramework.set(c.framework, [c]);
  }
  const hero = variant === 'hero';

  return (
    <section
      aria-label="Framework posture"
      data-testid="framework-posture-strip"
      className={cn('rounded-lg border border-border-subtle bg-surface-2 p-4', className)}
    >
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-muted">Framework posture</h3>
      <div className="flex flex-wrap gap-2">
        {FRAMEWORK_ORDER.filter((fw) => byFramework.has(fw)).map((fw) => (
          <FrameworkPill key={fw} framework={fw} counts={countByStatus(byFramework.get(fw) ?? [])} hero={hero} />
        ))}
      </div>

      {/* Compliance-lens hero variant: a first-2-controls-per-framework
          preview grid beneath the aggregate pills. */}
      {hero && (
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {FRAMEWORK_ORDER.filter((fw) => byFramework.has(fw)).flatMap((fw) =>
            (byFramework.get(fw) ?? []).slice(0, 2).map((c) => (
              <div
                key={`${c.framework}-${c.control_id}`}
                data-testid={`framework-preview-control-${c.framework}-${c.control_id}`}
                className="rounded-md border border-border-subtle bg-surface p-3 text-xs"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-text-muted">
                    {FRAMEWORK_LABEL[c.framework] ?? c.framework} {c.control_id}
                  </span>
                  <span
                    className={cn(
                      'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium',
                      STATUS_PILL_CLASS[c.status],
                    )}
                  >
                    <span className={cn('h-1.5 w-1.5 rounded-full', STATUS_DOT_CLASS[c.status])} aria-hidden="true" />
                    {c.status === 'not_measured' ? 'Not yet measured' : c.status}
                  </span>
                </div>
                <p className="mt-1 text-text-muted">{c.title}</p>
              </div>
            )),
          )}
        </div>
      )}
    </section>
  );
}
