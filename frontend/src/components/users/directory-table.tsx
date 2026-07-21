'use client';
/**
 * DirectoryTable — directory view table for /dashboard/users (Plan 14-04).
 *
 * Columns:
 *   selection checkbox · person (Avatar + display_name + email mono) ·
 *   Source (SourcePill for idp_source) · Title/Dept (job_title + department) ·
 *   Devices (device_count) · Risk (max_risk_score)
 *
 * Pitfall 7: the RBAC role field is NEVER rendered in this component.
 * Only job_title and department are displayed as the "role context" per D-USR-01.
 *
 * T-14-13: idp_source → SourcePill (literal Record lookup, no style injection).
 * Sunset tokens throughout; no raw palette utilities.
 */
import { cn } from '@/lib/utils';
import { Avatar } from '@/components/ui/Avatar';
import { SourcePill } from './source-pill';

// Re-export so the page can import DirectoryUser from directory-table.tsx
export type { DirectoryUser } from '@/lib/queries/use-directory-users';
import type { DirectoryUser } from '@/lib/queries/use-directory-users';

export type DirectoryTableProps = {
  users: DirectoryUser[];
  selectedIds: string[];
  onSelect: (id: string) => void;
  onSelectAll?: () => void;
};

function riskTokens(score: number): string {
  if (score >= 80) return 'text-[var(--color-severity-critical-on-soft)] border-severity-critical/30 bg-severity-critical/10';
  if (score >= 50) return 'text-[var(--color-severity-high-on-soft)] border-severity-high/30 bg-severity-high/10';
  if (score >= 20) return 'text-severity-medium border-severity-medium/30 bg-severity-medium/10';
  return 'text-severity-low border-severity-low/30 bg-severity-low/10';
}

export function DirectoryTable({
  users,
  selectedIds,
  onSelect,
  onSelectAll,
}: DirectoryTableProps) {
  const allSelected = users.length > 0 && users.every((u) => selectedIds.includes(u.id));

  return (
    <div className="overflow-x-auto rounded-lg border border-border-subtle" data-directory-table>
      <table className="w-full text-sm text-left">
        <thead className="border-b border-border-subtle bg-surface">
          <tr>
            <th className="w-10 px-4 py-3">
              {onSelectAll && (
                <input
                  type="checkbox"
                  aria-label="Select all"
                  checked={allSelected}
                  onChange={onSelectAll}
                  className="rounded border-border-subtle accent-violet"
                />
              )}
            </th>
            <th className="px-4 py-3 text-xs uppercase tracking-wide text-text-muted font-medium">
              Person
            </th>
            <th className="px-4 py-3 text-xs uppercase tracking-wide text-text-muted font-medium">
              Source
            </th>
            <th className="px-4 py-3 text-xs uppercase tracking-wide text-text-muted font-medium">
              Title / Dept
            </th>
            <th className="px-4 py-3 text-xs uppercase tracking-wide text-text-muted font-medium text-center">
              Devices
            </th>
            <th className="px-4 py-3 text-xs uppercase tracking-wide text-text-muted font-medium text-center">
              Risk
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border-subtle">
          {users.map((u) => {
            const isSelected = selectedIds.includes(u.id);
            const displayName = u.display_name || u.email;
            return (
              <tr
                key={u.id}
                data-user-row={u.id}
                className={cn(
                  'transition-colors',
                  isSelected ? 'bg-surface-2' : 'hover:bg-surface',
                  !u.is_active && 'opacity-50',
                )}
              >
                {/* Selection checkbox */}
                <td className="px-4 py-3">
                  <input
                    type="checkbox"
                    aria-label={`Select ${displayName}`}
                    checked={isSelected}
                    onChange={() => onSelect(u.id)}
                    className="rounded border-border-subtle accent-violet"
                  />
                </td>

                {/* Person: Avatar + display_name + email mono */}
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2.5">
                    <Avatar name={u.display_name ?? undefined} email={u.email} size={28} />
                    <div className="min-w-0">
                      <p className="font-medium text-text truncate">{displayName}</p>
                      <p className="text-xs font-mono text-text-faint truncate">{u.email}</p>
                    </div>
                  </div>
                </td>

                {/* Source — idp_source enrichment pill (D-USR-01) */}
                <td className="px-4 py-3">
                  <SourcePill source={u.idp_source} />
                </td>

                {/* Title / Dept — job_title + department only (Pitfall 7: RBAC field not shown) */}
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    {u.job_title && (
                      <span className="inline-flex items-center rounded-full border border-border-subtle bg-surface-2 px-2 py-0.5 text-xs text-text-muted">
                        {u.job_title}
                      </span>
                    )}
                    {u.department && (
                      <span className="inline-flex items-center rounded-full border border-border-subtle bg-surface-2 px-2 py-0.5 text-xs text-text-faint">
                        {u.department}
                      </span>
                    )}
                    {!u.job_title && !u.department && (
                      <span className="text-text-faint text-xs">—</span>
                    )}
                  </div>
                </td>

                {/* Devices */}
                <td className="px-4 py-3 text-center">
                  <span className="font-mono text-xs text-text-muted">
                    {u.device_count > 0 ? u.device_count : '—'}
                  </span>
                </td>

                {/* Risk score */}
                <td className="px-4 py-3 text-center">
                  {u.max_risk_score > 0 ? (
                    <span
                      className={cn(
                        'inline-flex items-center justify-center rounded border px-1.5 py-0.5 text-xs font-bold font-mono w-10',
                        riskTokens(u.max_risk_score),
                      )}
                    >
                      {u.max_risk_score}
                    </span>
                  ) : (
                    <span className="text-text-faint text-xs">—</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
