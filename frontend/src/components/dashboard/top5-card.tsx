'use client';
import Link from 'next/link';
import { Card } from '@/components/ui/card';
import { useTopTriage } from '@/lib/queries/use-top-triage';
import { microcopy } from './microcopy';
import { cn } from '@/lib/utils';

// D-T-01..05: Top 5 to triage — severity glyph (■/▲/◆/○), mono CVE id,
// truncated host, CVSS, SLA pill. Each row links to the drill route on
// /dashboard/vulnerabilities (Phase 11 honors ?open=drill).

const GLYPHS = { CRITICAL: '■', HIGH: '▲', MEDIUM: '◆', LOW: '○' } as const;
const GLYPH_COLOR = {
  CRITICAL: 'text-severity-critical',
  HIGH: 'text-severity-high',
  MEDIUM: 'text-severity-medium',
  LOW: 'text-severity-low',
} as const;

function slaPillClass(slaIso: string | null): string {
  if (!slaIso) return 'bg-surface-2 text-text-muted';
  const hours = (new Date(slaIso).getTime() - Date.now()) / 3_600_000;
  if (hours < 0) return 'bg-danger-soft text-danger';
  if (hours < 72) return 'bg-warning-soft text-warning';
  return 'bg-success-soft text-success';
}

function fmtSla(slaIso: string | null): string {
  if (!slaIso) return '—';
  const hours = (new Date(slaIso).getTime() - Date.now()) / 3_600_000;
  if (hours < 0) return `Breached ${Math.abs(Math.round(hours))}h ago`;
  if (hours < 48) return `${Math.round(hours)}h left`;
  return `${Math.round(hours / 24)}d left`;
}

export function Top5Card() {
  const q = useTopTriage(5);

  if (q.isPending) {
    return (
      <Card>
        <Card.Header>
          <h2 id="top5-h" className="text-lg font-semibold text-text">{microcopy.top5.h2}</h2>
        </Card.Header>
        <div aria-busy="true" className="h-64 animate-pulse rounded-md bg-surface-2" />
      </Card>
    );
  }

  if (q.error) {
    const code = (q.error as { code?: number | string } | null)?.code ?? 'unknown';
    const reqId = (q.error as { requestId?: string } | null)?.requestId ?? 'unknown';
    return (
      <Card>
        <Card.Header>
          <h2 id="top5-h" className="text-lg font-semibold text-text">{microcopy.top5.h2}</h2>
        </Card.Header>
        <p role="alert" className="text-sm">
          {microcopy.error.inline('Top 5', code, reqId)}
        </p>
      </Card>
    );
  }

  const items = q.data?.items ?? [];
  return (
    <Card>
      <Card.Header>
        <h2 id="top5-h" className="text-lg font-semibold text-text">{microcopy.top5.h2}</h2>
      </Card.Header>
      <ul aria-labelledby="top5-h" className="divide-y divide-border-subtle">
        {items.map((row) => (
          <li key={row.id}>
            <Link
              href={`/dashboard/vulnerabilities?cve=${encodeURIComponent(row.cve_id)}&open=drill`}
              className="grid grid-cols-[auto_1fr_auto_auto] items-center gap-3 px-1 py-3 hover:bg-surface-2 focus-visible:bg-surface-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-info"
            >
              <span
                className={cn('font-mono', GLYPH_COLOR[row.severity])}
                aria-label={row.severity.toLowerCase()}
              >
                {GLYPHS[row.severity]}
              </span>
              <div className="min-w-0">
                <p className="truncate font-mono text-sm text-text">{row.cve_id}</p>
                <p className="truncate font-mono text-xs text-text-muted">{row.host}</p>
              </div>
              <span className="font-mono text-sm text-text">
                {row.cvss_v3_score?.toFixed(1) ?? '—'}
              </span>
              <span className={cn('rounded-md px-2 py-0.5 font-mono text-xs', slaPillClass(row.sla_due_at))}>
                {fmtSla(row.sla_due_at)}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  );
}
