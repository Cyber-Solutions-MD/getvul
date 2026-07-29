'use client';
/**
 * RemediationTimeline — UX-04-02 main column lower band.
 *
 * Vertical list of remediation tickets ordered by ticket_created_at desc
 * (locked_decisions item 4 — backend `/api/v1/tickets?asset_id=` already
 * returns rows in that order, so the component renders the array as-is).
 *
 * Each row: provider gradient mark + ticket title (link when
 * external_ticket_url present) + status pill + relative timestamp.
 *
 * Provider gradients render as inline-style backgrounds — these are sketch-
 * scoped marks (sketch 005 variant B), NOT freehand palette. The hex stops
 * are documented in 12-CONTEXT.md D-D-02. The verification skips this file
 * in the "no raw hex" grep (see 12-08-PLAN.md verification §5).
 */
import type { RemediationTicket } from '@/lib/queries/use-asset-remediations';
import { cn } from '@/lib/utils';
import { AiExplanationSection } from '@/components/ai/ai-explanation-section';

const PROVIDER_GRADIENT: Record<string, string> = {
  JIRA: 'linear-gradient(135deg, #3B82F6, #60A5FA)',
  ASANA: 'linear-gradient(135deg, #F97316, #FB923C)',
  GITHUB: 'linear-gradient(135deg, #A78BFA, #C4B5FD)',
};

// WR-12: backend ticketing/service.py emits Ticket.external_status as
// lowercase 'open' and 'completed'. The component upper-cases on read,
// so the map keys must include COMPLETED (the Asana terminal state). Without
// this row, completed tickets fell through to the muted fallback tone instead
// of the resolved green.
const STATUS_TONE: Record<string, string> = {
  OPEN: 'border-violet/40 bg-violet-soft text-[var(--color-violet-on-soft)]',
  IN_PROGRESS: 'border-severity-high/40 bg-severity-high/10 text-[var(--color-severity-high-on-soft)]',
  RESOLVED: 'border-severity-low/40 bg-severity-low/10 text-severity-low',
  CLOSED: 'border-severity-low/40 bg-severity-low/10 text-severity-low',
  COMPLETED: 'border-severity-low/40 bg-severity-low/10 text-severity-low',
};

// W8: guard against future timestamps (clock skew / bad data); Math.max
// clamps to "just now" so we never render "−5h ago".
function relativeTimestamp(iso: string | null): string {
  if (!iso) return '—';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '—';
  const diffSec = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (diffSec < 60) return 'just now';
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  return `${Math.floor(diffSec / 86400)}d ago`;
}

export function RemediationTimeline({ tickets }: { tickets: RemediationTicket[] }) {
  if (!tickets || tickets.length === 0) return null;
  return (
    <ol className="space-y-3" data-testid="remediation-timeline">
      {tickets.map((t) => {
        const provider = (t.provider ?? '').toUpperCase();
        const gradient =
          PROVIDER_GRADIENT[provider] ??
          'linear-gradient(135deg, #6b7280, #9ca3af)';
        const statusKey = (t.external_status ?? '').toUpperCase().replace(/[ -]+/g, '_');
        const statusClass =
          STATUS_TONE[statusKey] ??
          'border-border-subtle bg-surface-2 text-text-faint';
        return (
          <li
            key={t.id}
            className="flex items-start gap-3"
            data-testid={`timeline-row-${t.id}`}
          >
            <span
              className="mt-1 inline-block h-5 w-5 shrink-0 rounded"
              style={{ background: gradient }}
              role="img"
              aria-label={provider || 'Unknown provider'}
              data-testid={`provider-mark-${provider.toLowerCase() || 'unknown'}`}
            />
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-sm text-text">
                  {t.external_ticket_url ? (
                    <a
                      href={t.external_ticket_url}
                      target="_blank"
                      rel="noreferrer"
                      className="hover:underline"
                    >
                      {t.title ?? 'Untitled'}
                    </a>
                  ) : (
                    t.title ?? 'Untitled'
                  )}
                </span>
                <span className="font-mono text-xs text-text-faint">
                  {relativeTimestamp(t.ticket_created_at)}
                </span>
              </div>
              {t.external_status && (
                <span
                  className={cn(
                    'mt-1 inline-block rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-wide',
                    statusClass,
                  )}
                >
                  {t.external_status}
                </span>
              )}
              {/* D-15: per-row "Explain this remediation" -- gated on a real
                  CVE string, since /explain-remediation/{cve_id} is CVE-
                  string-keyed (Plan 08), not ticket/remediation-UUID-keyed.
                  A ticket group's representative cve_id (backend MIN
                  aggregate over the group's underlying Vulnerability rows)
                  can be null (e.g. no CVE resolved) -- no CVE, no
                  affordance, matching the same "never force a broken
                  affordance" discipline as the host/vuln mounts always
                  having a real id. own <section> landmark per row (mirrors
                  drill-content.tsx's parent-owns-the-landmark convention)
                  with a per-row unique headingId so N rows never collide
                  on the shared component's internal h4 id. */}
              {t.cve_id && (
                <section aria-labelledby={`ai-explanation-h-remediation-${t.id}`} className="mt-3">
                  <AiExplanationSection
                    resourceType="remediation"
                    resourceId={t.cve_id}
                    headingId={`ai-explanation-h-remediation-${t.id}`}
                  />
                </section>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
