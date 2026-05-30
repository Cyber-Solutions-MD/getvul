/**
 * IdentityMetadataRail — UX-04-02 right-rail metadata block (host details).
 *
 * Stacked rows; each row is skipped when its value is null / undefined /
 * empty string (consumer never sees "—" rows here — they collapse). Reuses
 * the AssetDetail shape from Plan 12-05.
 *
 * Rendered as a `<section role="region" aria-label="Host metadata">` so the
 * screen-reader navigation hits it as a named landmark distinct from
 * RiskCard / OwnerCard.
 */
import type { AssetDetail } from '@/lib/queries/use-asset-detail';

function MetadataRow({
  label,
  value,
  mono,
}: {
  label: string;
  value: string | null | undefined;
  mono?: boolean;
}) {
  if (value === null || value === undefined || value === '') return null;
  return (
    <div className="flex items-baseline justify-between gap-3 border-t border-border-subtle py-2 text-xs">
      <span className="uppercase tracking-wide text-text-faint">{label}</span>
      <span className={mono ? 'font-mono text-text' : 'text-text'}>{value}</span>
    </div>
  );
}

export function IdentityMetadataRail({ asset }: { asset: AssetDetail }) {
  const ips = (asset.ip_addresses ?? []).join(', ');
  const macs = (asset.mac_addresses ?? []).join(', ');
  const os = asset.os_name
    ? `${asset.os_name}${asset.os_version ? ` ${asset.os_version}` : ''}`.trim()
    : null;
  return (
    <section
      className="rounded-lg border border-border-subtle bg-surface-2 p-4"
      aria-label="Host metadata"
      data-testid="identity-metadata"
    >
      <h3 className="mb-2 text-xs uppercase tracking-wide text-text-faint">
        Host details
      </h3>
      <MetadataRow label="Hostname" value={asset.hostname} mono />
      <MetadataRow label="IP" value={ips || undefined} mono />
      <MetadataRow label="MAC" value={macs || undefined} mono />
      <MetadataRow label="OS" value={os} />
      <MetadataRow label="Serial" value={asset.serial_number} mono />
      <MetadataRow label="Model" value={asset.model} />
      <MetadataRow label="Managed by" value={asset.managed_by} />
      <MetadataRow label="Last check-in" value={asset.last_checkin_at} mono />
      <MetadataRow label="Department" value={asset.department} />
      <MetadataRow label="Building" value={asset.building} />
    </section>
  );
}
