'use client';
/**
 * ConnectorCard — per-connector card for the /dashboard/connectors grid.
 *
 * D-CONN-05: displays ConnectorMark + connector_name + SyncStatusPill + last_sync_at
 *   formatted as relative time + last_sync_record_count.
 * D-CONN-06: Delete button rendered ONLY when isAdmin is true (backend enforces independently).
 * Sunset-tokenized: no raw gray-*, indigo-*, emerald-* utilities.
 *
 * T-14-08: Delete button is UX-layer gating; backend DELETE requires Admin.
 *
 * REL-06 (Plan 23-09): "health at a glance" additions —
 *   D-16: last_error inline summary, rendered ONLY on last_sync_status='failed'.
 *   D-17: frontend-derived "next sync in ~Xm" line (last_sync_at + sync_interval_minutes, no backend call).
 *   D-18: "failed N times in a row" from consecutive_failure_count (>1 threshold — a single failure is a blip).
 */
import { Play, Pencil, Trash2 } from 'lucide-react';
import { ConnectorMark } from './connector-mark';
import { SyncStatusPill } from './sync-status-pill';
import { cn } from '@/lib/utils';
import type { ConnectorConfigResponse } from '@/lib/queries/use-connectors-admin';
import type { ConnectorProvider } from './types';

/** Formats last_sync_at → "Synced 2h 14m ago" | "Just now" | "Never synced" */
function formatSyncTime(isoString: string | null): string {
  if (!isoString) return 'Never synced';
  const diffMs = Date.now() - new Date(isoString).getTime();
  const diffMin = Math.floor(diffMs / 60_000);
  if (diffMin < 1) return 'Synced just now';
  if (diffMin < 60) return `Synced ${diffMin}m ago`;
  const diffHrs = Math.floor(diffMin / 60);
  const remMin = diffMin % 60;
  if (diffHrs < 24) {
    return remMin > 0 ? `Synced ${diffHrs}h ${remMin}m ago` : `Synced ${diffHrs}h ago`;
  }
  const diffDays = Math.floor(diffHrs / 24);
  return `Synced ${diffDays}d ago`;
}

/**
 * D-17: frontend-derived "next sync in ~Xm" line — pure client math from
 * last_sync_at + sync_interval_minutes, no backend call.
 *   - last_sync_at null            -> "not synced yet"
 *   - computed next-sync in the past -> "sync due"
 *   - < 60m away                   -> "next sync in ~Xm"
 *   - >= 60m away                  -> "next sync in ~Xh"
 */
function nextSyncLabel(lastSyncAt: string | null, syncIntervalMinutes: number): string {
  if (!lastSyncAt) return 'not synced yet';
  const next = new Date(lastSyncAt).getTime() + syncIntervalMinutes * 60_000;
  const diffMs = next - Date.now();
  if (diffMs <= 0) return 'sync due';
  const diffMin = Math.round(diffMs / 60_000);
  if (diffMin < 60) return `next sync in ~${diffMin}m`;
  const diffHrs = Math.round(diffMin / 60);
  return `next sync in ~${diffHrs}h`;
}

export type ConnectorCardProps = {
  connector: ConnectorConfigResponse;
  isAdmin: boolean;
  onEdit: (connector: ConnectorConfigResponse) => void;
  onDelete: (connectorId: string) => void;
  onSync: (connectorId: string) => void;
  onToggleEnabled: (enabled: boolean) => void;
  isSyncing?: boolean;
};

export function ConnectorCard({
  connector,
  isAdmin,
  onEdit,
  onDelete,
  onSync,
  onToggleEnabled,
  isSyncing = false,
}: ConnectorCardProps) {
  const provider = connector.connector_type.toLowerCase() as ConnectorProvider;
  const syncTime = formatSyncTime(connector.last_sync_at);
  const nextSync = nextSyncLabel(connector.last_sync_at, connector.sync_interval_minutes);

  return (
    <div
      data-connector-card
      data-enabled={connector.is_enabled}
      className="rounded-lg border border-border-subtle bg-surface-2 p-4 transition-shadow hover:shadow-card"
    >
      {/* Header row: mark + name + status pill */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2.5">
          <ConnectorMark provider={provider} className="shrink-0" />
          <span className="truncate text-sm font-medium text-text">
            {connector.connector_name}
          </span>
        </div>
        <SyncStatusPill status={connector.last_sync_status} className="shrink-0" />
      </div>

      {/* Metadata row: last sync time + record count */}
      <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-text-muted">
        <span>{syncTime}</span>
        {connector.last_sync_record_count != null && (
          <span className="text-text-faint">
            {connector.last_sync_record_count.toLocaleString()} records
          </span>
        )}
      </div>

      {/* Next-sync line (D-17) — pure client math, no backend call */}
      <div className="mt-1 text-xs text-text-faint">{nextSync}</div>

      {/* Last-error summary (D-16) — ONLY on failure; healthy connectors render nothing here.
          Matches SyncStatusPill's failed=severity-critical convention (no amber here). */}
      {connector.last_sync_status === 'failed' && (
        <details className="mt-2 rounded-md border border-severity-critical/30 bg-severity-critical/10 px-2.5 py-1.5 text-xs">
          <summary className="cursor-pointer truncate text-[var(--color-severity-critical-on-soft)]">
            {connector.last_error || 'Last sync failed'}
          </summary>
          <div className="mt-1.5 space-y-1 text-text-muted">
            <p className="font-mono text-[11px] leading-snug text-[var(--color-severity-critical-on-soft)]">
              {connector.last_error || 'Last sync failed'}
            </p>
            <p className="text-text-faint">{syncTime}</p>
          </div>
          {/* D-18: a single failure is a blip; only surface a run of 2+ as a persistent-outage signal */}
          {connector.consecutive_failure_count > 1 && (
            <p className="mt-1 text-[var(--color-severity-critical-on-soft)]">
              failed {connector.consecutive_failure_count} times in a row
            </p>
          )}
        </details>
      )}

      {/* Actions row */}
      <div className="mt-3 flex items-center gap-2">
        {/* Sync now */}
        <button
          type="button"
          onClick={() => onSync(connector.id)}
          disabled={isSyncing}
          className={cn(
            'inline-flex items-center gap-1.5 rounded-md border border-border-subtle px-2.5 py-1.5 text-xs text-text-muted transition-colors',
            'hover:border-border hover:text-text',
            'disabled:cursor-not-allowed disabled:opacity-50',
          )}
        >
          <Play size={12} aria-hidden />
          Sync now
        </button>

        {/* Edit */}
        <button
          type="button"
          onClick={() => onEdit(connector)}
          className="inline-flex items-center gap-1.5 rounded-md border border-border-subtle px-2.5 py-1.5 text-xs text-text-muted transition-colors hover:border-border hover:text-text"
        >
          <Pencil size={12} aria-hidden />
          Edit
        </button>

        {/* Enable/Disable toggle — sunset switch pattern */}
        <button
          type="button"
          onClick={() => onToggleEnabled(!connector.is_enabled)}
          aria-label={connector.is_enabled ? 'Disable connector' : 'Enable connector'}
          className={cn(
            'relative ml-auto inline-flex h-5 w-9 items-center rounded-full border transition-colors',
            connector.is_enabled
              ? 'border-transparent [background:var(--gradient-sunset)]'
              : 'border-border-subtle bg-surface',
          )}
        >
          <span
            className={cn(
              'inline-block size-3.5 rounded-full bg-white shadow transition-transform',
              connector.is_enabled ? 'translate-x-[18px]' : 'translate-x-[2px]',
            )}
          />
        </button>

        {/* Delete — Admin only (T-14-08, D-CONN-06) */}
        {isAdmin && (
          <button
            type="button"
            onClick={() => onDelete(connector.id)}
            aria-label="Delete connector"
            className="inline-flex items-center gap-1.5 rounded-md border border-border-subtle px-2.5 py-1.5 text-xs text-text-muted transition-colors hover:border-severity-critical/40 hover:text-[var(--color-severity-critical-on-soft)]"
          >
            <Trash2 size={12} aria-hidden />
            Delete
          </button>
        )}
      </div>
    </div>
  );
}
