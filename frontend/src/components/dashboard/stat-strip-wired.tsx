'use client';
import { ShieldAlert, Clock, Flame, TrendingDown } from 'lucide-react';
import { Stat } from '@/components/ui/stat';
import { StatStrip } from '@/components/ui/stat-strip';
import { useStats } from '@/lib/queries/use-stats';
import { microcopy } from './microcopy';

// D-S-05: data-bound StatStrip. 4 tiles with locked icon + deltaIsGood mapping.
// mttr_30d.value is a server-formatted string ('4.2d') per Plan 01 Open Q2.
// All four tiles have deltaIsGood='down' — fewer criticals / SLA risks / KEVs /
// shorter MTTR are all wins for the analyst.

export function StatStripWired() {
  const q = useStats();

  if (q.isPending) {
    return (
      <section aria-labelledby="stats-h">
        <h2 id="stats-h" className="sr-only">{microcopy.stats.h2}</h2>
        <div
          aria-busy="true"
          className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4"
        >
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-28 rounded-lg bg-surface-2 animate-pulse" />
          ))}
        </div>
      </section>
    );
  }

  if (q.error) {
    const code = (q.error as { code?: number | string } | null)?.code ?? 'unknown';
    const reqId = (q.error as { requestId?: string } | null)?.requestId ?? 'unknown';
    return (
      <section aria-labelledby="stats-h">
        <h2 id="stats-h" className="sr-only">{microcopy.stats.h2}</h2>
        <p
          role="alert"
          className="rounded-lg border border-danger bg-danger-soft p-3 text-sm"
        >
          {microcopy.error.inline('Stats', code, reqId)}
        </p>
      </section>
    );
  }

  const t = q.data!.dashboard_tiles;

  return (
    <section aria-labelledby="stats-h">
      <h2 id="stats-h" className="sr-only">{microcopy.stats.h2}</h2>
      <StatStrip>
        <Stat
          label={microcopy.stats.labels.critical_open}
          value={t.critical_open.value as number}
          delta={t.critical_open.delta}
          deltaIsGood="down"
          deltaSuffix={microcopy.stats.deltaSuffix}
          icon={<ShieldAlert className="h-4 w-4" />}
        />
        <Stat
          label={microcopy.stats.labels.sla_at_risk}
          value={t.sla_at_risk.value as number}
          delta={t.sla_at_risk.delta}
          deltaIsGood="down"
          deltaSuffix={microcopy.stats.deltaSuffix}
          icon={<Clock className="h-4 w-4" />}
        />
        <Stat
          label={microcopy.stats.labels.kev}
          value={t.kev.value as number}
          delta={t.kev.delta}
          deltaIsGood="down"
          deltaSuffix={microcopy.stats.deltaSuffix}
          icon={<Flame className="h-4 w-4" />}
        />
        <Stat
          label={microcopy.stats.labels.mttr_30d}
          value={String(t.mttr_30d.value)}
          delta={null}
          deltaIsGood="down"
          icon={<TrendingDown className="h-4 w-4" />}
        />
      </StatStrip>
    </section>
  );
}
