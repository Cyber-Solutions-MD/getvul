'use client';
/**
 * ControlCard — one framework-control status card (Phase 43 Plan 01,
 * RPT-03). Presentation-only: consumes a `ControlStatus` row from
 * use-compliance.ts and NEVER re-derives status client-side (the backend
 * catalog evaluator is the single source of truth for pass/partial/fail/
 * not_measured — 43-RESEARCH.md Architectural Responsibility Map).
 *
 * Layout locked by 43-UI-SPEC.md "RPT-03 -- /dashboard/compliance page":
 *   [framework glyph] SOC 2 CC7.1                    [* Pass]
 *   Vulnerability detection & monitoring
 *   Evidenced by: Scanner coverage of your inventory -- currently 97%
 *
 * Not clickable (D-13 explicitly defers drill-into-findings evidence this
 * phase). Long control name / evidencing line wrap freely -- the card
 * GROWS to fit (E2/E3 long-text) -- never clipped.
 */
import { cn } from '@/lib/utils';
import type { ControlStatus } from '@/lib/queries/use-compliance';

const FRAMEWORK_LABEL: Record<string, string> = {
  soc2: 'SOC 2',
  iso27001: 'ISO 27001',
  pci_dss: 'PCI DSS',
  nist_csf: 'NIST CSF',
};

// Small colored square per framework (visual-language.md's provider-mark
// idiom, simplified to a flat square -- "not a real logo").
const FRAMEWORK_GLYPH_CLASS: Record<string, string> = {
  soc2: 'bg-violet',
  iso27001: 'bg-pink',
  pci_dss: 'bg-amber',
  nist_csf: 'bg-severity-info',
};

// 4-state palette per 43-UI-SPEC.md Color -- NOTE this page uses the
// success/warning/danger semantic tokens verbatim (not the amber/
// severity-critical ticket-status family), exactly as the UI-SPEC locks.
const STATUS_CONFIG: Record<ControlStatus['status'], { classes: string; label: string }> = {
  pass: { classes: 'border-success/40 bg-success/10 text-success', label: 'Pass' },
  partial: { classes: 'border-warning/40 bg-warning/10 text-warning', label: 'Partial' },
  fail: { classes: 'border-danger/40 bg-danger/10 text-danger', label: 'Fail' },
  not_measured: {
    classes: 'border-dashed border-border bg-surface-2 text-text-faint',
    label: 'Not yet measured',
  },
};

const METRIC_LABEL: Record<string, string> = {
  coverage_pct: 'Scanner coverage of your inventory',
  sla_compliance_pct: 'SLA compliance (last 90 days)',
  critical_sla_health_pct: 'Critical/high SLA health',
  has_active_scanning: 'Active vulnerability scanning',
  mttr_by_tier: 'Remediation time vs. your SLA tiers',
};

function evidencingLine(control: ControlStatus): string {
  const metricLabel = METRIC_LABEL[control.metric_key] ?? control.metric_key;
  if (control.status === 'not_measured' || control.value === null) {
    return `Not yet measured — ${metricLabel}.`;
  }
  if (control.metric_key === 'has_active_scanning') {
    return `${metricLabel}: ${control.value === 1 ? 'Yes' : 'No'}`;
  }
  return `${metricLabel}: ${control.value}%`;
}

export type ControlCardProps = {
  control: ControlStatus;
  className?: string;
};

export function ControlCard({ control, className }: ControlCardProps) {
  const statusConfig = STATUS_CONFIG[control.status];
  const frameworkLabel = FRAMEWORK_LABEL[control.framework] ?? control.framework;
  const glyphClass = FRAMEWORK_GLYPH_CLASS[control.framework] ?? 'bg-text-faint';

  return (
    <div
      data-control-card
      data-framework={control.framework}
      data-control-status={control.status}
      className="rounded-lg border border-border-subtle bg-surface-2 p-6"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <span aria-hidden="true" className={cn('inline-block size-3.5 shrink-0 rounded-sm', glyphClass)} />
          <span className="truncate text-sm text-text">
            {frameworkLabel} <span className="font-mono">{control.control_id}</span>
          </span>
        </div>
        <span
          data-status-pill
          className={cn(
            'inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium',
            statusConfig.classes,
          )}
        >
          <span aria-hidden="true" className="size-1.5 rounded-full bg-current" />
          {statusConfig.label}
        </span>
      </div>

      <p className="mt-3 text-sm font-semibold text-text">{control.title}</p>

      <p className="mt-1 text-sm text-text-muted">
        <span className="font-mono">{evidencingLine(control)}</span>
      </p>
    </div>
  );
}
