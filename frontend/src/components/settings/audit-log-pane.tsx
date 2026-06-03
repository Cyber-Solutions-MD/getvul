'use client';
/**
 * AuditLogPane — D-SET-09 filtered + paginated read-only audit log table.
 *
 * Filters (debounced text inputs + selects):
 *   action / resource_type / user_email → useAuditLog(opts)
 *
 * Table columns:
 *   actor (user_email + Avatar) · action (mono) · target (resource_type/resource_id mono) · timestamp
 *
 * State patterns (mandatory):
 *   isPending → SkeletonTable
 *   empty     → EmptyState ("No audit events match these filters")
 *   error     → PartialFailureBanner
 *
 * Pagination: page_size 50, next/prev controls.
 *
 * No raw palette utilities (gray-N / indigo-N).
 * data-pane="audit" for test hooks.
 *
 * Plan 14-05.
 */

import { useState, useCallback, useEffect } from 'react';
import { useAuditLog } from '@/lib/queries/use-audit-log';
import { SkeletonTable } from '@/components/states';
import { EmptyState } from '@/components/states';
import { PartialFailureBanner } from '@/components/states';
import { Avatar } from '@/components/ui/Avatar';
import { queryKeys } from '@/lib/queries/keys';

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatRelativeDate(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  const diffMs = Date.now() - d.getTime();
  const diffMins = Math.floor(diffMs / 60_000);
  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHrs = Math.floor(diffMins / 60);
  if (diffHrs < 24) {
    const mins = diffMins % 60;
    return mins > 0 ? `${diffHrs}h ${mins}m ago` : `${diffHrs}h ago`;
  }
  const diffDays = Math.floor(diffHrs / 24);
  return `${diffDays}d ago`;
}

// ── Component ─────────────────────────────────────────────────────────────────

export function AuditLogPane() {
  const [action, setAction] = useState('');
  const [resourceType, setResourceType] = useState('');
  const [userEmail, setUserEmail] = useState('');
  const [page, setPage] = useState(1);

  const { data, isPending, isError, refetch } = useAuditLog({
    action: action || undefined,
    resource_type: resourceType || undefined,
    user_email: userEmail || undefined,
    page,
  });

  const handleFilterChange = useCallback(() => {
    setPage(1);
  }, []);

  const items = data?.items ?? [];
  const totalPages = data?.pages ?? 0;

  // WR-05: after a fetch, if the current page exceeds the available pages
  // (e.g. a filter narrowed the result set while paginated past the new end),
  // clamp back to the last valid page. Guarded by totalPages > 0 so the
  // transient "Page 1 of 0" state during a refetch never triggers a snap.
  useEffect(() => {
    if (totalPages > 0 && page > totalPages) {
      setPage(totalPages);
    }
  }, [totalPages, page]);

  return (
    <div data-pane="audit" className="space-y-4 p-6">
      {/* Error banner */}
      {isError && (
        <PartialFailureBanner
          watchKeys={[
            queryKeys.settings.auditLog({
              action: action || undefined,
              resource_type: resourceType || undefined,
              user_email: userEmail || undefined,
              page,
            }),
          ]}
          onRetry={refetch}
        />
      )}

      {/* Filter inputs */}
      <div className="flex flex-wrap gap-3">
        {/* Action filter */}
        <select
          value={action}
          onChange={(e) => { setAction(e.target.value); handleFilterChange(); }}
          className="rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-text focus:border-violet focus:outline-none"
        >
          <option value="">All actions</option>
          <option value="auth">Auth</option>
          <option value="vuln">Vulnerabilities</option>
          <option value="ticket">Tickets</option>
          <option value="user">Users</option>
          <option value="settings">Settings</option>
          <option value="connector">Connectors</option>
          <option value="rule">Rules</option>
        </select>

        {/* Resource type filter */}
        <select
          value={resourceType}
          onChange={(e) => { setResourceType(e.target.value); handleFilterChange(); }}
          className="rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-text focus:border-violet focus:outline-none"
        >
          <option value="">All resources</option>
          <option value="user">User</option>
          <option value="vulnerability">Vulnerability</option>
          <option value="remediation">Remediation</option>
          <option value="ticket">Ticket</option>
          <option value="connector">Connector</option>
          <option value="setting">Setting</option>
        </select>

        {/* User email filter */}
        <input
          type="email"
          value={userEmail}
          onChange={(e) => { setUserEmail(e.target.value); handleFilterChange(); }}
          placeholder="Filter by actor email"
          className="flex-1 rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-text placeholder-text-faint focus:border-violet focus:outline-none"
        />

        {data && (
          <span className="ml-auto self-center text-xs text-text-faint">
            {data.total.toLocaleString()} events
          </span>
        )}
      </div>

      {/* Loading skeleton */}
      {isPending && (
        <SkeletonTable
          rows={8}
          columns={[
            { kind: 'text', width: 120 },
            { kind: 'mono', width: 160 },
            { kind: 'text', width: 100 },
            { kind: 'mono', width: 80 },
          ]}
        />
      )}

      {/* Empty state */}
      {!isPending && !isError && items.length === 0 && (
        <EmptyState>
          <EmptyState.Title>No audit events match these filters</EmptyState.Title>
          <EmptyState.Body>
            Try adjusting the action, resource type, or email filters above.
          </EmptyState.Body>
        </EmptyState>
      )}

      {/* Table */}
      {!isPending && items.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-border-subtle">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border-subtle bg-surface">
              <tr>
                <th className="px-4 py-3 text-xs font-medium uppercase tracking-wide text-text-faint">
                  Actor
                </th>
                <th className="px-4 py-3 text-xs font-medium uppercase tracking-wide text-text-faint">
                  Action
                </th>
                <th className="px-4 py-3 text-xs font-medium uppercase tracking-wide text-text-faint">
                  Target
                </th>
                <th className="px-4 py-3 text-xs font-medium uppercase tracking-wide text-text-faint">
                  When
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {items.map((log) => (
                <tr
                  key={log.id}
                  className="bg-surface hover:bg-surface-2 transition-colors"
                >
                  {/* Actor */}
                  <td className="px-4 py-2">
                    <div className="flex items-center gap-2">
                      <Avatar email={log.user_email ?? undefined} size={24} />
                      <span className="font-mono text-xs text-text">
                        {log.user_email ?? 'system'}
                      </span>
                    </div>
                  </td>
                  {/* Action */}
                  <td className="px-4 py-2">
                    <span className="font-mono text-xs text-text-muted">
                      {log.action}
                    </span>
                  </td>
                  {/* Target */}
                  <td className="px-4 py-2">
                    <span className="text-xs text-text-muted">
                      {log.resource_type ?? '—'}
                      {log.resource_id && (
                        <span className="font-mono text-text-faint">
                          {' #'}{log.resource_id.substring(0, 8)}
                        </span>
                      )}
                    </span>
                  </td>
                  {/* Timestamp */}
                  <td className="px-4 py-2">
                    <span className="font-mono text-xs text-text-faint">
                      {formatRelativeDate(log.created_at)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
            className="rounded-lg border border-border bg-surface-2 px-3 py-1.5 text-sm text-text-muted hover:text-text disabled:cursor-not-allowed disabled:opacity-40"
          >
            Previous
          </button>
          <span className="text-sm text-text-faint">
            Page {page} of {totalPages}
          </span>
          <button
            type="button"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
            className="rounded-lg border border-border bg-surface-2 px-3 py-1.5 text-sm text-text-muted hover:text-text disabled:cursor-not-allowed disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
