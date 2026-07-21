/**
 * TicketAssetCard — rail card that cross-links to /assets/{assetId}.
 *
 * UX-05-04: right-rail Asset card on /tickets/[id].
 * - Renders hostname (mono), OS name, risk score.
 * - Link to /assets/{assetId} ("View asset →").
 * - When assetId is null (ticket spans multiple hosts), renders
 *   "Multiple hosts" summary with no single link.
 *
 * No inline hex — all colors via Tailwind sunset tokens.
 */
import Link from 'next/link';
import { microcopy } from './microcopy';

export type TicketAssetCardProps = {
  assetId: string | null;
  hostname: string | null;
  osName: string | null;
  riskScore: number | null;
};

export function TicketAssetCard({
  assetId,
  hostname,
  osName,
  riskScore,
}: TicketAssetCardProps) {
  if (!assetId) {
    return (
      <div className="rounded-xl border border-border-subtle bg-surface-2 p-4">
        <p className="text-sm text-text-muted">{microcopy.multipleHosts}</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border-subtle bg-surface-2 p-4 space-y-3">
      {/* Hostname — mono per design system (terminal-pasteable value) */}
      {hostname && (
        <p className="font-mono text-sm font-medium text-text truncate" title={hostname}>
          {hostname}
        </p>
      )}

      {/* OS name */}
      {osName && (
        <p className="text-xs text-text-muted">{osName}</p>
      )}

      {/* Risk score */}
      {riskScore !== null && (
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-text-muted">Risk</span>
          <span className="font-mono text-sm font-semibold text-text">{riskScore}</span>
        </div>
      )}

      {/* Cross-link to asset detail */}
      <Link
        href={`/dashboard/assets/${assetId}`}
        className="inline-flex items-center text-xs text-[var(--color-violet-on-soft)] hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-violet rounded"
      >
        {microcopy.viewAsset}
      </Link>
    </div>
  );
}
