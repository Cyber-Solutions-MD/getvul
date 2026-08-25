'use client';
/**
 * ExportBoardReportDialog — Phase 43 Plan 03 (RPT-01 D-03/D-04 web UI). The
 * on-demand "Export board report" dialog that drives Plan 02's extended
 * `/api/v1/export/summary` PDF (risk trend / MTTR-by-tier / SLA compliance
 * chart sections) and the pre-existing `ScheduledReport` CRUD
 * (`/api/v1/reports`). Opened by this plan's caller today and by the RPT-02
 * leadership lens CTA in Plan 04 — this component owns no page-level state,
 * only `open`/`onOpenChange`.
 *
 * Analogs (43-PATTERNS.md): exception-grant-dialog.tsx (ResponsiveDialog +
 * FIELD_CLASS/FIELD_LABEL_CLASS idiom, reset-on-open effect), scope-window-
 * controls.tsx (preset toggle + native-date custom range, plain useState),
 * ExportButton.tsx (auth'd blob-download fetch + 401-refresh-retry),
 * notifications-pane.tsx (checkbox-reveals-inline-fields disclosure).
 *
 * Design decisions not spelled out verbatim by the plan (documented here so
 * the "why" survives a re-read):
 *
 * 1. "Existing board ScheduledReport" detection: `ScheduledReport` has no
 *    dedicated "is this the board report" flag. This dialog identifies it by
 *    `sections` containing `'risk_trend'` (an RPT-01-only section key) —
 *    deterministic and content-based, not name-based (robust against a user
 *    renaming the report).
 *
 * 2. "Retry with charts off (tables only)" (E4/E9 error contract) is
 *    implemented WITHOUT any backend change: `export_resource` already
 *    defaults to the full 9-section list (the 6 original + the 3 new RPT-01
 *    sections) when no `section` query param is sent at all, and
 *    `_collect_summary_data` only computes/draws a section when its key is
 *    present (43-02-SUMMARY.md "Gated computation"). So the normal submit
 *    sends NO `section` params (accepting the full default), and the
 *    charts-off retry explicitly sends the original 6 non-chart section keys
 *    — which drops the 3 chart-bearing sections entirely, i.e. "tables
 *    only". This reuses the pre-existing `section` query param mechanism; it
 *    does not touch the also-pre-existing-but-unwired `charts_enabled`
 *    internal filter key (that would require a new backend query param,
 *    which is out of this plan's `files_modified`).
 *
 * 3. Editing an ALREADY-persisted schedule's cadence/recipients is out of
 *    this plan's scope (the plan only specifies enable-via-POST and
 *    disable-via-DELETE/E7). To avoid a misleading always-editable field
 *    that silently doesn't persist, the cadence/recipients fields render
 *    read-only (disabled) once a persisted board ScheduledReport exists.
 *    Un-checking still works (opens the E7 confirm) regardless.
 */
import { useEffect, useState } from 'react';
import { Download, Loader2, X } from 'lucide-react';
import { ResponsiveDialog } from '@/components/ui/responsive-dialog';
import { api, API_URL } from '@/lib/api';
import { cn } from '@/lib/utils';

type PeriodPreset = '30d' | '90d' | 'quarter' | 'year' | 'custom';
type Cadence = 'daily' | 'weekly' | 'monthly';

type ScheduledReportRow = {
  id: string;
  schedule: string;
  recipients: string[] | null;
  sections: string[] | null;
};

export type ExportBoardReportDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

// D-03: presets mirror Phase 42's range-control idiom; default is `quarter`
// ("Last quarter" — board cadence, 43-UI-SPEC.md RPT-01 PDF Rendering
// Contract). Ids match `export_resource`'s `period` query-param pattern
// (`^(30d|90d|quarter|year)$`) verbatim.
const PERIOD_OPTIONS: { id: PeriodPreset; label: string }[] = [
  { id: '30d', label: 'Last 30 days' },
  { id: '90d', label: 'Last 90 days' },
  { id: 'quarter', label: 'Last quarter' },
  { id: 'year', label: 'Last year' },
  { id: 'custom', label: 'Custom range' },
];

const CADENCE_OPTIONS: { id: Cadence; label: string }[] = [
  { id: 'daily', label: 'Daily' },
  { id: 'weekly', label: 'Weekly' },
  { id: 'monthly', label: 'Monthly' },
];

// The original 6-section default (pre-Plan-02) — sent explicitly ONLY on the
// "retry with charts off" path to override the backend's own now-9-section
// default and drop the 3 chart-bearing sections. See module doc, point 2.
const NO_CHART_SECTIONS = ['vulns', 'assets', 'risk', 'top_hosts', 'top_remediations', 'tickets'];

// The 3 RPT-01 sections created by Plan 02; used only to identify an
// existing "board" ScheduledReport (see module doc, point 1) and to compose
// the payload of a newly-created one.
const BOARD_SECTIONS = [...NO_CHART_SECTIONS, 'risk_trend', 'mttr_by_tier', 'sla_compliance'];
const BOARD_REPORT_NAME = 'Board report';

// Mirrors exception-grant-dialog.tsx:61-62 / scope-window-controls.tsx:59-61
// — the codebase's established native <input>/<select> styling convention.
const FIELD_CLASS =
  'w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-text placeholder-text-faint focus:border-violet focus:outline-none disabled:cursor-not-allowed disabled:opacity-60';
const FIELD_LABEL_CLASS = 'mb-1 block text-xs font-semibold uppercase tracking-wide text-text-muted';

function parseRecipients(value: string): string[] {
  return value
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
}

function isCustomRangeValid(from: string, to: string): boolean {
  return !!from && !!to && to >= from;
}

/** Reuses ExportButton.tsx's authenticated blob-download fetch (401-refresh-
 * retry) verbatim, extended with the D-03 period query params and the
 * charts-off section override. Throws on any non-2xx / network failure so
 * the caller's single try/catch renders the UI-SPEC error copy. */
async function downloadBoardReportPdf(params: {
  periodPreset: PeriodPreset;
  customFrom: string;
  customTo: string;
  chartsOff: boolean;
}): Promise<void> {
  const stored = typeof window !== 'undefined' ? localStorage.getItem('getvul_token') : null;
  if (!stored && process.env.NODE_ENV === 'production') {
    if (typeof window !== 'undefined') window.location.href = '/login';
    return;
  }
  const token = stored || 'dev-token';

  const qs = new URLSearchParams({ format: 'pdf' });
  if (params.periodPreset === 'custom') {
    qs.set('from', params.customFrom);
    qs.set('to', params.customTo);
  } else {
    qs.set('period', params.periodPreset);
  }
  if (params.chartsOff) {
    for (const s of NO_CHART_SECTIONS) qs.append('section', s);
  }

  const url = `${API_URL}/api/v1/export/summary?${qs}`;
  let resp = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });

  if (resp.status === 401) {
    const refresh = typeof window !== 'undefined' ? localStorage.getItem('getvul_refresh') : null;
    if (refresh) {
      const rr = await fetch(`${API_URL}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refresh }),
      });
      if (rr.ok) {
        const data = await rr.json();
        localStorage.setItem('getvul_token', data.access_token);
        resp = await fetch(url, { headers: { Authorization: `Bearer ${data.access_token}` } });
      } else {
        if (typeof window !== 'undefined') window.location.href = '/login';
        throw new Error('Session expired.');
      }
    } else {
      if (typeof window !== 'undefined') window.location.href = '/login';
      throw new Error('Session expired.');
    }
  }

  if (!resp.ok) {
    throw new Error(`Export failed with status ${resp.status}`);
  }

  const blob = await resp.blob();
  const disposition = resp.headers.get('Content-Disposition') || '';
  const filename = disposition.match(/filename=(.+)/)?.[1] || 'getvul_board_report.pdf';

  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = objectUrl;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(objectUrl);
}

export function ExportBoardReportDialog({ open, onOpenChange }: ExportBoardReportDialogProps) {
  const [periodPreset, setPeriodPreset] = useState<PeriodPreset>('quarter');
  const [customFrom, setCustomFrom] = useState('');
  const [customTo, setCustomTo] = useState('');

  const [schedulingChecked, setSchedulingChecked] = useState(false);
  const [existingReport, setExistingReport] = useState<ScheduledReportRow | null>(null);
  const [cadence, setCadence] = useState<Cadence>('weekly');
  const [recipients, setRecipients] = useState('');
  const [showStopConfirm, setShowStopConfirm] = useState(false);
  const [isStoppingSchedule, setIsStoppingSchedule] = useState(false);

  const [isGenerating, setIsGenerating] = useState(false);
  const [generationError, setGenerationError] = useState<string | null>(null);

  // Reset to a fresh state every time the dialog opens (mirrors exception-
  // grant-dialog.tsx's reset-on-open convention) and seed the scheduling
  // toggle from the tenant's existing ScheduledReport rows, if any.
  useEffect(() => {
    if (!open) return;
    setPeriodPreset('quarter');
    setCustomFrom('');
    setCustomTo('');
    setGenerationError(null);
    setIsGenerating(false);
    setShowStopConfirm(false);
    setExistingReport(null);
    setSchedulingChecked(false);
    setCadence('weekly');
    setRecipients('');

    let cancelled = false;
    api<ScheduledReportRow[]>('/api/v1/reports')
      .then((reports) => {
        if (cancelled) return;
        const board = (reports ?? []).find((r) => Array.isArray(r.sections) && r.sections.includes('risk_trend'));
        if (board) {
          setExistingReport(board);
          setSchedulingChecked(true);
          setCadence((board.schedule as Cadence) || 'weekly');
          setRecipients((board.recipients ?? []).join(', '));
        }
      })
      .catch(() => {
        // Non-fatal — seeding the scheduling toggle is a convenience; the
        // dialog still functions with the default unchecked state.
      });
    return () => {
      cancelled = true;
    };
  }, [open]);

  const rangeOrderError = !!customFrom && !!customTo && customTo < customFrom;
  const periodValid = periodPreset !== 'custom' || isCustomRangeValid(customFrom, customTo);
  const wouldCreateNewSchedule = schedulingChecked && !existingReport;
  const scheduleValid = !wouldCreateNewSchedule || parseRecipients(recipients).length > 0;
  const canSubmit = !isGenerating && periodValid && scheduleValid;

  function handleToggleScheduling(nextChecked: boolean) {
    if (!nextChecked && existingReport) {
      // Unchecking an ALREADY-persisted schedule is destructive (E7) — open
      // the confirm instead of unchecking immediately. Because we never flip
      // `schedulingChecked` here, "Cancel" needs no explicit re-check step.
      setShowStopConfirm(true);
      return;
    }
    setSchedulingChecked(nextChecked);
  }

  function handleStopSendingCancel() {
    setShowStopConfirm(false);
  }

  async function handleStopSendingConfirm() {
    if (!existingReport) return;
    setIsStoppingSchedule(true);
    try {
      await api(`/api/v1/reports/${existingReport.id}`, { method: 'DELETE' });
      setExistingReport(null);
      setSchedulingChecked(false);
      setShowStopConfirm(false);
    } catch {
      // Left open — the fixed two-button confirm has no dedicated error
      // copy; "Stop sending" simply remains clickable to retry.
    } finally {
      setIsStoppingSchedule(false);
    }
  }

  async function handleExport(chartsOff: boolean) {
    if (!canSubmit) return;
    setIsGenerating(true);
    setGenerationError(null);
    try {
      if (wouldCreateNewSchedule) {
        const created = await api<ScheduledReportRow>('/api/v1/reports', {
          method: 'POST',
          body: JSON.stringify({
            name: BOARD_REPORT_NAME,
            schedule: cadence,
            format: 'pdf',
            recipients: parseRecipients(recipients),
            sections: BOARD_SECTIONS,
          }),
        });
        setExistingReport(created);
      }
      await downloadBoardReportPdf({ periodPreset, customFrom, customTo, chartsOff });
      onOpenChange(false);
    } catch {
      setGenerationError(
        'Board report generation failed. Try again — if chart rendering keeps failing, retry with charts off (tables only).',
      );
    } finally {
      setIsGenerating(false);
    }
  }

  // ── E7: destructive confirm — swaps the SAME dialog's content (not a
  // nested second overlay) so only one role="dialog" is ever mounted. ──
  if (showStopConfirm) {
    const stopCadence = existingReport?.schedule || cadence;
    return (
      <ResponsiveDialog
        open={open}
        onOpenChange={(o) => {
          if (!o) handleStopSendingCancel();
        }}
        ariaLabel="Stop scheduled board report"
      >
        <div className="p-2 min-[768px]:p-0">
          <h3 className="text-lg font-semibold text-text">Stop scheduled board report</h3>
          <p className="mt-2 text-sm text-text-muted">
            Recipients will stop receiving the <span className="font-mono">{stopCadence}</span> board report — you
            can re-enable it any time.
          </p>
          <div className="mt-6 flex justify-end gap-3 pb-[env(safe-area-inset-bottom)]">
            <button
              type="button"
              onClick={handleStopSendingCancel}
              className="rounded-lg border border-border-subtle px-4 py-2 text-sm text-text-muted hover:text-text hover:bg-surface transition"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleStopSendingConfirm}
              disabled={isStoppingSchedule}
              className="rounded-lg px-4 py-2 text-sm font-medium bg-severity-critical text-white hover:bg-severity-critical/90 transition focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-surface-2 disabled:pointer-events-none disabled:opacity-50"
            >
              Stop sending
            </button>
          </div>
        </div>
      </ResponsiveDialog>
    );
  }

  const titleId = 'export-board-report-title';

  return (
    <ResponsiveDialog open={open} onOpenChange={onOpenChange} ariaLabelledBy={titleId}>
      <div className="p-6">
        <div className="mb-4 flex items-start justify-between gap-4">
          <h2 id={titleId} className="text-lg font-semibold text-text">
            Export board report
          </h2>
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            aria-label="Close"
            className="rounded-md p-1 text-text-faint transition-colors hover:text-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
          >
            <X size={18} />
          </button>
        </div>

        {generationError && (
          <div role="alert" className="mb-4 rounded-md border border-danger/40 bg-danger-soft px-3 py-2 text-xs text-danger">
            <p className="font-semibold">Board report generation failed.</p>
            <p className="mt-1">Try again — if chart rendering keeps failing, retry with charts off (tables only).</p>
            <div className="mt-2 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => handleExport(false)}
                className="rounded-md border border-danger/40 px-2 py-1 text-xs font-medium text-danger hover:bg-danger/10"
              >
                Retry
              </button>
              <button
                type="button"
                onClick={() => handleExport(true)}
                className="rounded-md border border-danger/40 px-2 py-1 text-xs font-medium text-danger hover:bg-danger/10"
              >
                Retry with charts off (tables only)
              </button>
            </div>
          </div>
        )}

        <div className="space-y-4">
          {/* Period (D-03) */}
          <div>
            <span className={FIELD_LABEL_CLASS}>Period</span>
            <div
              role="group"
              aria-label="Report period"
              className="inline-flex flex-wrap rounded-md border border-border-subtle p-0.5"
            >
              {PERIOD_OPTIONS.map((o) => {
                const active = o.id === periodPreset;
                return (
                  <button
                    key={o.id}
                    type="button"
                    aria-pressed={active}
                    onClick={() => setPeriodPreset(o.id)}
                    className={cn(
                      'rounded-sm border-b-2 px-3 py-1 text-xs font-medium transition-colors',
                      active
                        ? 'border-violet bg-surface-2 text-text'
                        : 'border-transparent text-text-muted hover:text-text',
                    )}
                  >
                    {o.label}
                  </button>
                );
              })}
            </div>

            {periodPreset === 'custom' && (
              <div className="mt-2 flex flex-wrap items-end gap-3 rounded-md border border-border-subtle bg-surface-2 p-3">
                <div>
                  <label htmlFor="export-board-report-from" className={FIELD_LABEL_CLASS}>
                    From
                  </label>
                  <input
                    id="export-board-report-from"
                    type="date"
                    value={customFrom}
                    onChange={(e) => setCustomFrom(e.target.value)}
                    className={FIELD_CLASS}
                  />
                </div>
                <div>
                  <label htmlFor="export-board-report-to" className={FIELD_LABEL_CLASS}>
                    To
                  </label>
                  <input
                    id="export-board-report-to"
                    type="date"
                    value={customTo}
                    onChange={(e) => setCustomTo(e.target.value)}
                    className={FIELD_CLASS}
                  />
                </div>
                {rangeOrderError && (
                  <p role="alert" className="text-xs text-danger">
                    &apos;To&apos; must not be before &apos;From&apos;.
                  </p>
                )}
              </div>
            )}
          </div>

          {/* D-04 scheduling disclosure — btn-secondary weight, never
              competing visually with the gradient CTA below. */}
          <div className="rounded-md border border-border-subtle bg-surface p-3">
            <label className="flex items-center gap-2 text-sm text-text-muted">
              <input
                type="checkbox"
                checked={schedulingChecked}
                onChange={(e) => handleToggleScheduling(e.target.checked)}
                className="rounded border-border"
              />
              Also send this report <span className="font-mono">{cadence}</span> by email
            </label>

            {schedulingChecked && (
              <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <label htmlFor="export-board-report-cadence" className={FIELD_LABEL_CLASS}>
                    Cadence
                  </label>
                  <select
                    id="export-board-report-cadence"
                    value={cadence}
                    disabled={!!existingReport}
                    onChange={(e) => setCadence(e.target.value as Cadence)}
                    className={FIELD_CLASS}
                  >
                    {CADENCE_OPTIONS.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor="export-board-report-recipients" className={FIELD_LABEL_CLASS}>
                    Recipients
                  </label>
                  <input
                    id="export-board-report-recipients"
                    type="text"
                    value={recipients}
                    disabled={!!existingReport}
                    onChange={(e) => setRecipients(e.target.value)}
                    placeholder="ciso@company.com, board@company.com"
                    className={FIELD_CLASS}
                  />
                  {!existingReport && (
                    <p className="mt-1 text-xs text-text-muted">Comma-separated.</p>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="rounded-lg border border-border-subtle px-4 py-2 text-sm text-text-muted hover:text-text hover:bg-surface transition"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => handleExport(false)}
            disabled={!canSubmit}
            className="btn-cta inline-flex items-center justify-center gap-1.5 rounded-md bg-gradient-sunset px-4 py-2 text-sm font-medium text-text-inverse shadow-glow-cta hover:opacity-95 focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet disabled:pointer-events-none disabled:opacity-50"
          >
            {isGenerating ? (
              <>
                <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                Generating…
              </>
            ) : (
              <>
                <Download className="size-4" aria-hidden="true" />
                Export board report
              </>
            )}
          </button>
        </div>
      </div>
    </ResponsiveDialog>
  );
}
