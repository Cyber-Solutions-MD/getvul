'use client';
/**
 * TicketDrillContent — D-D-01 slot content for the shared DrillPanel chrome.
 *
 * Renders the ticket drill body: header (provider mark + mono ID + title + close),
 * body (linked-vulns mini-list, description, status+SLA row), and a sticky footer
 * (Open in provider / Open full detail / blocked-toggle slot).
 *
 * Presentational only — no data fetching. The caller (tickets list page, Plan 07)
 * passes the ticket summary from the list row. Full detail wired in /tickets/[id].
 *
 * T-13-16: externalUrl rendered as href text node via React — no dangerouslySetInnerHTML.
 * T-13-17: ticketId passed from list row (caller-controlled, not raw URL param).
 */
import { X } from 'lucide-react';
import Link from 'next/link';
import { ProviderMark } from './provider-mark';
import { StatusPill } from './status-pill';
import { SlaPill } from './sla-pill';
import type { TicketProvider } from './types';

// ── Types ────────────────────────────────────────────────────────────────────

export type LinkedVuln = {
  cveId: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  cvss: number;
};

/** Minimal ticket shape consumed by the drill panel. Caller (list row) supplies this. */
export type TicketDrillData = {
  provider: TicketProvider;
  externalId: string;
  title: string;
  /** Backend-controlled external URL for "Open in provider" link (T-13-16). */
  externalUrl: string;
  externalStatus: string | null;
  blocked: boolean;
  slaDueAt: string | null;
  description: string | null;
  /** Top 3 by severity (caller pre-sorts; component renders in order). */
  linkedVulns: LinkedVuln[];
  /** Total linked vuln count (may exceed linkedVulns.length). Used for +N more. */
  totalVulns: number;
};

type TicketDrillContentProps = {
  ticketId: string;
  ticket?: TicketDrillData;
  onClose: () => void;
  /**
   * Slot for the blocked toggle (wired in Plan 06/08).
   * When not provided, renders a disabled "Mark blocked" placeholder.
   */
  renderBlockedToggle?: (args: { ticketId: string }) => React.ReactNode;
};

// ── Severity glyphs (visual-language.md) ────────────────────────────────────

const SEVERITY_GLYPH: Record<LinkedVuln['severity'], string> = {
  critical: '■',
  high: '▲',
  medium: '◆',
  low: '○',
  info: '□',
};

const SEVERITY_CLASS: Record<LinkedVuln['severity'], string> = {
  critical: 'text-[var(--color-severity-critical-on-soft)]',
  high: 'text-[var(--color-severity-high-on-soft)]',
  medium: 'text-severity-medium',
  low: 'text-severity-low',
  info: 'text-severity-info',
};

// Provider name capitalized for "Open in Jira" copy (copy-voice.md: peer-not-butler)
const PROVIDER_LABEL: Record<TicketProvider, string> = {
  jira: 'Jira',
  asana: 'Asana',
  github: 'GitHub',
};

// ── Component ────────────────────────────────────────────────────────────────

export function TicketDrillContent({
  ticketId,
  ticket,
  onClose,
  renderBlockedToggle,
}: TicketDrillContentProps) {
  if (!ticket) {
    return (
      <div aria-busy="true" className="p-6 text-text-muted text-sm">
        Loading…
      </div>
    );
  }

  const {
    provider,
    externalId,
    title,
    externalUrl,
    externalStatus,
    blocked,
    slaDueAt,
    description,
    linkedVulns,
    totalVulns,
  } = ticket;

  const providerLabel = PROVIDER_LABEL[provider];
  const topVulns = linkedVulns.slice(0, 3);
  const moreCount = totalVulns - topVulns.length;
  const detailHref = `/tickets/${ticketId}`;

  return (
    <div className="flex h-full flex-col">
      {/* ── Header ── */}
      <div className="flex items-start justify-between border-b border-border-subtle px-5 py-4">
        <div className="flex min-w-0 flex-1 items-start gap-2">
          <ProviderMark provider={provider} className="mt-0.5 shrink-0" />
          <div className="min-w-0">
            <span className="font-mono text-sm font-semibold text-text">
              {externalId}
            </span>
            <p className="mt-0.5 truncate text-sm text-text-muted">{title}</p>
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="ml-2 shrink-0 rounded-md p-1 text-text-muted hover:bg-surface-2 hover:text-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
        >
          <X size={18} aria-hidden="true" />
        </button>
      </div>

      {/* ── Body ── */}
      <div className="flex-1 space-y-5 overflow-y-auto p-5">
        {/* Linked vulns mini-list (top 3) */}
        <section aria-labelledby="tdrill-vulns-h">
          <h4
            id="tdrill-vulns-h"
            className="mb-2 text-xs uppercase tracking-wide text-text-muted"
          >
            Linked vulnerabilities
          </h4>
          <ul className="space-y-1">
            {topVulns.map((v) => (
              <li
                key={v.cveId}
                className="flex items-center gap-2 text-sm"
                style={{ minHeight: '28px' }}
              >
                <span
                  className={SEVERITY_CLASS[v.severity]}
                  aria-label={v.severity}
                >
                  {SEVERITY_GLYPH[v.severity]}
                </span>
                <span className="font-mono text-text">{v.cveId}</span>
                <span className="ml-auto font-mono text-xs text-text-muted">
                  {v.cvss.toFixed(1)}
                </span>
              </li>
            ))}
          </ul>
          {moreCount > 0 && (
            <Link
              href={detailHref}
              className="mt-1 block text-xs text-text-muted hover:text-text"
            >
              +{moreCount} more
            </Link>
          )}
        </section>

        {/* Status + SLA pills */}
        <section aria-labelledby="tdrill-status-h">
          <h4
            id="tdrill-status-h"
            className="mb-2 text-xs uppercase tracking-wide text-text-muted"
          >
            Status
          </h4>
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill externalStatus={externalStatus} blocked={blocked} />
            <SlaPill dueAt={slaDueAt} />
          </div>
        </section>

        {/* Description (line-clamp-6) + Show full link */}
        {description && (
          <section aria-labelledby="tdrill-desc-h">
            <h4
              id="tdrill-desc-h"
              className="mb-2 text-xs uppercase tracking-wide text-text-muted"
            >
              Description
            </h4>
            <p className="line-clamp-6 text-sm text-text">{description}</p>
            <Link
              href={detailHref}
              className="mt-1 block text-xs text-text-muted hover:text-text"
            >
              Show full →
            </Link>
          </section>
        )}
      </div>

      {/* ── Footer (sticky bottom) ── */}
      <div className="flex flex-col gap-2 border-t border-border-subtle p-4">
        {/* T-13-16: externalUrl is a backend-controlled URL from the connector.
            Rendered as a text-node href — no dangerouslySetInnerHTML. */}
        <a
          href={externalUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center justify-center gap-1.5 rounded-md border border-border bg-surface-2 px-4 py-2 text-sm font-medium text-text hover:bg-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
        >
          Open in {providerLabel}
        </a>
        <Link
          href={detailHref}
          className="inline-flex items-center justify-center gap-1.5 rounded-md bg-gradient-sunset px-4 py-2 text-sm font-medium text-text-inverse shadow-glow-cta hover:opacity-95 focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
        >
          Open full detail
        </Link>
        {renderBlockedToggle
          ? renderBlockedToggle({ ticketId })
          : (
            <button
              type="button"
              disabled
              className="inline-flex items-center justify-center gap-1.5 rounded-md border border-border bg-surface-2 px-4 py-2 text-sm font-medium text-text-muted opacity-50 cursor-not-allowed"
            >
              Mark blocked
            </button>
          )}
      </div>
    </div>
  );
}
