'use client';
import Link from 'next/link';
import { Zap, Clock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { microcopy } from './microcopy';
import { useSnoozeMutation } from '@/lib/mutations/use-snooze';
import { useUndoSnoozeMutation } from '@/lib/mutations/use-undo-snooze';
import { useStats } from '@/lib/queries/use-stats';
import { useToast } from '@/components/ui/ToastProvider';

// D-H-01..12 — action-first hero: pulsing-dot eyebrow + headline + sub-line +
// CTA pair (Start triage gradient + Snooze 1h secondary), OR quiet-win at zero
// criticals, OR loading skeleton, OR inline-error fallback. Each section in the
// dashboard owns its own loading/error states (D-D-11 + D-E-02); the page-level
// ErrorBoundary catches *thrown* errors only.

export function Hero() {
  const stats = useStats();
  const snooze = useSnoozeMutation();
  const undoSnooze = useUndoSnoozeMutation();
  const { toast } = useToast();

  if (stats.isPending) {
    return (
      <section
        aria-busy="true"
        aria-labelledby="hero-h"
        className="h-40 rounded-lg bg-surface-2 animate-pulse"
      >
        <h2 id="hero-h" className="sr-only">Action required</h2>
      </section>
    );
  }

  if (stats.error) {
    const code = (stats.error as { code?: number | string } | null)?.code ?? 'unknown';
    const reqId = (stats.error as { requestId?: string } | null)?.requestId ?? 'unknown';
    return (
      <section
        role="alert"
        aria-labelledby="hero-h"
        className="rounded-lg border border-danger bg-danger-soft p-5 text-sm"
      >
        <h2 id="hero-h" className="sr-only">Action required</h2>
        {microcopy.error.inline('Hero', code, reqId)}
      </section>
    );
  }

  const data = stats.data!;
  const n = data.dashboard_tiles.critical_open.value as number;
  const topVuln = data.top_vuln;

  if (n === 0) {
    return (
      <section aria-labelledby="hero-h" className="rounded-lg border border-border-subtle bg-surface p-6">
        <div className="mb-2 flex items-center gap-2">
          <span className="block h-2 w-2 rounded-full bg-success" aria-hidden="true" />
          <span className="text-xs uppercase tracking-wide text-text-muted">Status</span>
        </div>
        <h2 id="hero-h" className="text-3xl font-semibold text-text">
          {microcopy.hero.quietWin}
        </h2>
      </section>
    );
  }

  const headline = n === 1 ? microcopy.hero.headlineSingular : microcopy.hero.headlinePlural(n);
  // BL-01: backend declares host/path/cvss as nullable on TopVuln. Only render
  // the sub-line when host AND path are present — without those the sentence
  // doesn't make sense ("Top one is on null — null, CVSS 0.0"). cvss may still
  // be null and is handled inside subLineTemplate (renders '—').
  const subLine =
    topVuln && topVuln.host && topVuln.path
      ? microcopy.hero.subLineTemplate(
          topVuln.host,
          topVuln.path,
          topVuln.cvss !== null ? Number(topVuln.cvss) : null,
          topVuln.exploited
        )
      : null;

  const onSnooze = async () => {
    if (!topVuln) return;
    try {
      await snooze.mutateAsync({ id: topVuln.id });
      toast({
        message: microcopy.snooze.toastMessage(topVuln.cve_id),
        variant: 'success',
        duration: 8000,
        action: {
          label: microcopy.snooze.toastActionLabel,
          onClick: () => undoSnooze.mutate({ id: topVuln.id }),
        },
      });
    } catch (e) {
      const status = (e as { status?: number } | null)?.status ?? 'unknown';
      toast({
        message: microcopy.snooze.toastError(status),
        variant: 'error',
      });
    }
  };

  return (
    <section aria-labelledby="hero-h" className="rounded-lg border border-border-subtle bg-surface p-6">
      <div className="mb-2 flex items-center gap-2">
        {/* D-H-05 — pulsing red when criticalOpen > 0; honors prefers-reduced-motion via globals.css */}
        <span
          className="block h-2 w-2 rounded-full bg-severity-critical animate-pulse"
          aria-hidden="true"
        />
        <span className="text-xs uppercase tracking-wide text-text-muted">Action required</span>
      </div>
      <h2 id="hero-h" className="text-3xl font-semibold text-text">{headline}</h2>
      {subLine && (
        <p className="mt-2 line-clamp-2 text-base text-text-muted" title={subLine}>
          {subLine}
        </p>
      )}
      <div className="mt-4 flex flex-wrap gap-3">
        <Button asChild variant="cta">
          {/* asChild drops leftIcon affordance — render Zap inline inside the Link.
              Button's base class adds gap-2 so flex spacing is preserved. */}
          <Link href="/dashboard/vulnerabilities?status=open&severity=critical">
            <Zap aria-hidden />
            {microcopy.hero.ctaPrimary}
          </Link>
        </Button>
        {topVuln && (
          <Button
            variant="secondary"
            leftIcon={<Clock />}
            onClick={onSnooze}
            loading={snooze.isPending}
            loadingText="Snoozing…"
          >
            {microcopy.hero.ctaSecondary}
          </Button>
        )}
      </div>
    </section>
  );
}
