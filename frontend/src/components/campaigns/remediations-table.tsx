'use client';
/**
 * RemediationsTable — CAMP-01 entry-point table for the brand-new
 * /dashboard/vulnerabilities/remediations page (zero prior frontend
 * consumers of GET /remediations/grouped, 38-RESEARCH.md Pitfall 8).
 *
 * Columns: remediation label (mono, remediation_action falling back to the
 * bare remediation_id) · affected hosts (mono, tabular-nums) · member count
 * (mono, tabular-nums, singularized at M=1 — vuln_count is this row's
 * "findings" total, matching CampaignsTable's own "Members" column
 * convention) · max severity (glyph, reusing tickets/severity-glyph.ts's
 * SEVERITY_GLYPH/SEVERITY_CLASS maps verbatim) · a `Start campaign` CTA.
 *
 * This component NEVER imports/calls useRouter or fires the mutation
 * itself — `onStartCampaign` is a prop, mirroring CampaignsTable/
 * TicketsTable's "table renders, page owns side effects" contract.
 *
 * T-38-09 (XSS): remediation_action/remediation_id render as React text
 * children (no dangerouslySetInnerHTML) — React auto-escapes them.
 */
import { SEVERITY_GLYPH, SEVERITY_CLASS } from '@/components/tickets/severity-glyph';
import { cn } from '@/lib/utils';
import type { RemediationGroup } from '@/lib/queries/use-remediations-grouped';

export type RemediationsTableProps = {
  rows: RemediationGroup[];
  onStartCampaign: (remediationId: string) => void;
  /** Disables every row's CTA while a start-campaign mutation is in flight. */
  isStarting?: boolean;
};

// Singularizes a count string per the zero-one-many gotcha flagged
// throughout 38-UI-SPEC.md ("never '1 findings'").
function countLabel(n: number, singular: string): string {
  return n === 1 ? `1 ${singular}` : `${n} ${singular}s`;
}

export function RemediationsTable({ rows, onStartCampaign, isStarting = false }: RemediationsTableProps) {
  return (
    <table className="w-full border-collapse text-sm">
      <thead className="sticky top-0 z-10 bg-surface">
        <tr className="border-b border-border-subtle text-left text-xs uppercase tracking-wide text-text-muted">
          <th scope="col" className="px-3 py-2" data-col="remediation">
            Remediation
          </th>
          <th scope="col" className="px-3 py-2" data-col="hosts">
            Hosts
          </th>
          <th scope="col" className="px-3 py-2" data-col="members">
            Members
          </th>
          <th scope="col" className="px-3 py-2" data-col="severity">
            Severity
          </th>
          <th scope="col" className="px-3 py-2" data-col="action">
            <span className="sr-only">Actions</span>
          </th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => {
          const label = r.remediation_action || r.remediation_id;
          const sevKey = r.max_severity.toLowerCase();
          return (
            <tr
              key={r.remediation_id}
              className="border-b border-border-subtle hover:bg-surface-2"
            >
              {/* Remediation label — mono, truncated with full string on
                  hover (backstop: "Long remediation label -> ellipsis +
                  full string in title tooltip"). */}
              <td className="px-3 py-3 max-w-[360px]">
                <span className="block truncate font-mono text-text" title={label}>
                  {label}
                </span>
              </td>
              <td className="px-3 py-3 font-mono tabular-nums text-text-muted">
                {r.affected_hosts}
              </td>
              <td className="px-3 py-3 font-mono tabular-nums text-text-muted">
                {countLabel(r.vuln_count, 'finding')}
              </td>
              <td className="px-3 py-3">
                <span
                  role="img"
                  aria-label={r.max_severity}
                  className={cn('font-mono tabular-nums', SEVERITY_CLASS[sevKey] ?? 'text-text-faint')}
                >
                  {SEVERITY_GLYPH[sevKey] ?? '□'}
                </span>
              </td>
              <td className="px-3 py-3 text-right">
                <button
                  type="button"
                  disabled={isStarting}
                  onClick={() => onStartCampaign(r.remediation_id)}
                  className={cn(
                    'inline-flex items-center gap-1.5 rounded-md bg-gradient-sunset px-3 py-1.5 text-xs font-medium text-text-inverse shadow-glow-cta',
                    'hover:opacity-95 focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet',
                    'disabled:pointer-events-none disabled:opacity-50',
                  )}
                >
                  Start campaign
                </button>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
