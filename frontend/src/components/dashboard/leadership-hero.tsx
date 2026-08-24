'use client';
/**
 * LeadershipHero — RPT-02 leadership-lens widget (Phase 43 Plan 04, item 1
 * of 5). Same hero SLOT as `hero.tsx` (analyst/IT-ops), swapped content per
 * 43-UI-SPEC.md: "Export board report" gradient CTA replaces the hero's
 * "Start triage" CTA for this lens only. Opens Plan 03's
 * `ExportBoardReportDialog` — this component owns only the dialog's
 * open/close boolean, no export logic of its own (the dialog is a complete,
 * standalone, already-tested unit per 43-03-SUMMARY.md).
 */
import { useState } from 'react';
import { Download } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ExportBoardReportDialog } from './export-board-report-dialog';

export function LeadershipHero() {
  const [exportOpen, setExportOpen] = useState(false);

  return (
    <section aria-labelledby="leadership-hero-h" className="rounded-lg border border-border-subtle bg-surface p-6">
      <div className="mb-2 flex items-center gap-2">
        <span className="text-xs uppercase tracking-wide text-text-muted">Leadership view</span>
      </div>
      <h2 id="leadership-hero-h" className="text-3xl font-semibold text-text">
        Program posture, board-ready
      </h2>
      <p className="mt-2 text-base text-text-muted">
        Risk trend, remediation speed, and framework posture — exportable for the next board review.
      </p>
      <div className="mt-4 flex flex-wrap gap-3">
        <Button variant="cta" leftIcon={<Download />} onClick={() => setExportOpen(true)}>
          Export board report
        </Button>
      </div>

      <ExportBoardReportDialog open={exportOpen} onOpenChange={setExportOpen} />
    </section>
  );
}
