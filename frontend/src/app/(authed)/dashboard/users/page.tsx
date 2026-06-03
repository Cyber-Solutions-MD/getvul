'use client';
/**
 * /dashboard/users — People directory + groups (Plan 14-04 rewrite).
 *
 * D-USR-01: directory rows show idp_source pill + job_title/department chip.
 *           RBAC role NOT displayed here (Pitfall 7) — lives in Workspace settings.
 * D-USR-02: export-only bulk bar (ExportButton resource="users").
 * D-USR-03: Directory/Groups segmented toggle (no horizontal tabs), ?view= URL.
 * D-X-01: loading→SkeletonTable, empty→EmptyState, error→PartialFailureBanner.
 * D-X-02: snake_case throughout.
 * T-14-13: ChipBar axis allowLists clamp reflected URL values.
 *
 * v1 surface (horizontal tabs, raw palette, inline fetch) fully replaced.
 */
import { useState, useCallback, useEffect, Suspense } from 'react';
import { useRouter, usePathname, useSearchParams } from 'next/navigation';
import { useUrlState } from '@/hooks/use-url-state';
import { useUrlStateList } from '@/hooks/use-url-state-list';
import { cn } from '@/lib/utils';
import { ChipBar } from '@/components/ui/ChipBar';
import type { ChipAxis } from '@/components/ui/ChipBar';
import {
  SkeletonTable,
  EmptyState,
  PartialFailureBanner,
} from '@/components/states';
import { DirectoryTable } from '@/components/users/directory-table';
import { UsersExportBar } from '@/components/users/users-export-bar';
import { microcopy } from '@/components/users/microcopy';
import { useDirectoryUsers, useDirectoryStats } from '@/lib/queries/use-directory-users';
import { useTenantGroups } from '@/lib/queries/use-tenant-groups';
import { queryKeys } from '@/lib/queries/keys';
import ExportButton from '@/components/ui/ExportButton';

// View toggle values — used in allowList (T-14-13)
const VIEWS = ['directory', 'groups'] as const;
type View = (typeof VIEWS)[number];

// Status chips — hardcoded allowList (T-14-13)
const STATUS_ALLOW = ['active', 'suspended', 'all'] as const;

// Source chips — hardcoded allowList (T-14-13)
const SOURCE_ALLOW = ['google', 'azure', 'okta', 'humaans', 'local'] as const;

// Skeleton columns for directory table loading state
const DIRECTORY_SKELETON_COLUMNS = [
  { kind: 'pill' as const, width: 28 },
  { kind: 'text' as const, width: 200 },
  { kind: 'pill' as const, width: 70 },
  { kind: 'text' as const, width: 160 },
  { kind: 'mono' as const, width: 40 },
  { kind: 'mono' as const, width: 40 },
];

function buildUsersAxes(stats: {
  departments?: Array<{ name: string; count: number }>;
  by_source?: Record<string, number>;
} | null | undefined): ChipAxis[] {
  // Department allow-list: derive from stats; static fallback if stats not loaded yet.
  // Values from server are still clamped by useUrlStateList on read (T-14-13).
  const deptAllowList = stats?.departments?.map((d) => d.name) ?? [];
  const deptCounts: Record<string, number> = {};
  stats?.departments?.forEach((d) => { deptCounts[d.name] = d.count; });

  // Source allow-list: static enum + actual source keys from stats
  const sourceAllowList = [
    ...SOURCE_ALLOW,
    ...Object.keys(stats?.by_source ?? {}).filter(
      (s) => !(SOURCE_ALLOW as readonly string[]).includes(s)
    ),
  ];
  const sourceCounts = stats?.by_source ?? {};

  return [
    {
      key: 'status',
      label: 'Status',
      allowList: STATUS_ALLOW,
      chips: [
        { value: 'active', label: 'Active' },
        { value: 'suspended', label: 'Suspended' },
        { value: 'all', label: 'All' },
      ],
    },
    ...(deptAllowList.length > 0
      ? [{
          key: 'department',
          label: 'Dept',
          allowList: deptAllowList,
          counts: deptCounts,
          derivedFromCounts: true,
        }]
      : []),
    {
      key: 'source',
      label: 'Source',
      allowList: sourceAllowList,
      counts: sourceCounts,
      derivedFromCounts: true,
    },
  ];
}

function UsersPageInner() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  // D-USR-03: Directory / Groups segmented toggle — URL ?view=
  const [view, setView] = useUrlState<View>('view', VIEWS, 'directory');

  // Directory filter URL state
  const [statusValues] = useUrlStateList<string>('status', STATUS_ALLOW, []);
  const status = statusValues[0] ?? 'active';

  const [departmentValues] = useUrlStateList<string>('department', [], []);
  const department = departmentValues[0] ?? '';

  const [sourceValues] = useUrlStateList<string>('source', SOURCE_ALLOW, []);
  const source = sourceValues[0] ?? '';

  const searchParam = params?.get('search') ?? '';

  // WR-01: real pagination state. Reset to page 1 whenever a filter changes so
  // a narrower result set never leaves us stranded on an out-of-range page.
  const [page, setPage] = useState(1);
  useEffect(() => {
    setPage(1);
  }, [status, department, source, searchParam]);

  // Row selection state
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  // Stats (for chip-bar axes)
  const statsQuery = useDirectoryStats();

  // Directory data
  const directoryQuery = useDirectoryUsers({
    filters: {
      status: status !== 'active' ? status : undefined,
      department: department || undefined,
      source: source || undefined,
      search: searchParam || undefined,
    },
    page,
    sort: 'display_name',
    order: 'asc',
  });

  // Stable list of items the selection handlers operate on (WR-02). Deriving
  // this and depending on it keeps handleSelectAll from closing over a stale
  // query reference captured on the first render.
  const items = directoryQuery.data?.items ?? [];
  const totalPages = directoryQuery.data?.pages ?? 0;

  // WR-05-style clamp: if the current page exceeds the available pages after a
  // fetch (e.g. result set shrank), snap back to the last valid page.
  useEffect(() => {
    if (totalPages > 0 && page > totalPages) {
      setPage(totalPages);
    }
  }, [totalPages, page]);

  const handleSelect = useCallback((id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  }, []);

  const handleSelectAll = useCallback(() => {
    setSelectedIds((prev) =>
      prev.length === items.length ? [] : items.map((u) => u.id)
    );
  }, [items]);

  const handleClearSelection = useCallback(() => setSelectedIds([]), []);

  // Groups data
  const groupsQuery = useTenantGroups();

  const usersAxes = buildUsersAxes(statsQuery.data);

  return (
    <div className="space-y-5">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight text-text">
          Users
        </h1>
      </div>

      {/* D-USR-03: Segmented toggle (NOT horizontal tabs) */}
      <div
        role="group"
        aria-label="View"
        className="inline-flex rounded-full border border-border-subtle bg-surface p-0.5"
      >
        <button
          type="button"
          onClick={() => setView('directory')}
          aria-pressed={view === 'directory'}
          className={cn(
            'rounded-full px-4 py-1 text-xs font-medium transition-colors',
            'focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet',
            view === 'directory'
              ? 'bg-surface-2 text-text'
              : 'text-text-muted hover:text-text',
          )}
        >
          {microcopy.directoryView}
        </button>
        <button
          type="button"
          onClick={() => setView('groups')}
          aria-pressed={view === 'groups'}
          className={cn(
            'rounded-full px-4 py-1 text-xs font-medium transition-colors',
            'focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet',
            view === 'groups'
              ? 'bg-surface-2 text-text'
              : 'text-text-muted hover:text-text',
          )}
        >
          {microcopy.groupsView}
        </button>
      </div>

      {/* ── Directory view ─────────────────────────────────────────── */}
      {view === 'directory' && (
        <>
          {/* Chip-bar filters: status / department / source + search */}
          <ChipBar
            axes={usersAxes}
            showSearch
            searchPlaceholder={microcopy.searchPlaceholder}
            searchAriaLabel={microcopy.searchAriaLabel}
          />

          {/* State: loading */}
          {directoryQuery.isPending && (
            <SkeletonTable columns={DIRECTORY_SKELETON_COLUMNS} rows={8} />
          )}

          {/* State: error */}
          {directoryQuery.isError && (
            <PartialFailureBanner
              watchKeys={[
                queryKeys.directoryUsers.list({
                  filters: {},
                  page: 1,
                  sort: 'display_name',
                  order: 'asc',
                }),
              ]}
              onRetry={() => directoryQuery.refetch()}
            />
          )}

          {/* State: empty */}
          {!directoryQuery.isPending &&
            !directoryQuery.isError &&
            directoryQuery.data?.items.length === 0 && (
              <EmptyState>
                <EmptyState.Title>{microcopy.emptyState.title}</EmptyState.Title>
                <EmptyState.Body>{microcopy.emptyState.body}</EmptyState.Body>
                <EmptyState.Actions>
                  <button
                    type="button"
                    className="rounded-md bg-gradient-sunset px-4 py-2 text-sm font-medium text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
                    onClick={() => {
                      const sp = new URLSearchParams();
                      router.replace(
                        `${pathname}?${sp.toString()}`,
                        { scroll: false }
                      );
                    }}
                  >
                    {microcopy.emptyState.clearAll}
                  </button>
                </EmptyState.Actions>
                <EmptyState.Suggestion>
                  {microcopy.emptyState.suggestion}
                </EmptyState.Suggestion>
              </EmptyState>
            )}

          {/* Data: directory table */}
          {!directoryQuery.isPending &&
            !directoryQuery.isError &&
            directoryQuery.data &&
            directoryQuery.data.items.length > 0 && (
              <DirectoryTable
                users={directoryQuery.data.items}
                selectedIds={selectedIds}
                onSelect={handleSelect}
                onSelectAll={handleSelectAll}
              />
            )}

          {/* Pagination (WR-01) — mirrors audit-log-pane controls */}
          {!directoryQuery.isPending &&
            !directoryQuery.isError &&
            totalPages > 1 && (
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

          {/* Export-only bulk bar — D-USR-02 */}
          <UsersExportBar
            selectedIds={selectedIds}
            onClearSelection={handleClearSelection}
          />
        </>
      )}

      {/* ── Groups view ────────────────────────────────────────────── */}
      {view === 'groups' && (
        <div className="space-y-4">
          {/* Groups header + export */}
          <div className="flex items-center justify-between">
            <span className="text-sm text-text-muted">
              {groupsQuery.isPending
                ? 'Loading groups…'
                : groupsQuery.isError
                  ? 'Groups unavailable'
                  : `${groupsQuery.data?.length ?? 0} groups`}
            </span>
            <ExportButton
              resource="groups"
              label={microcopy.exportGroups}
            />
          </div>

          {/* Loading */}
          {groupsQuery.isPending && (
            <SkeletonTable
              columns={[
                { kind: 'text' as const, width: 200 },
                { kind: 'mono' as const, width: 60 },
              ]}
              rows={6}
            />
          )}

          {/* Error (WR-07): D-X-01 mandates an explicit error state — the
              groups view previously hung on "Loading groups…" forever. */}
          {groupsQuery.isError && (
            <PartialFailureBanner
              watchKeys={[queryKeys.settings.groups()]}
              onRetry={() => groupsQuery.refetch()}
            />
          )}

          {/* Groups list */}
          {!groupsQuery.isPending &&
            !groupsQuery.isError &&
            groupsQuery.data &&
            groupsQuery.data.length > 0 && (
            <div className="space-y-2">
              {groupsQuery.data.map((g) => (
                <div
                  key={g.name}
                  className="flex items-center justify-between rounded-lg border border-border-subtle bg-surface px-4 py-3"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-medium text-text">{g.name}</span>
                  </div>
                  <span className="rounded-full border border-border-subtle bg-surface-2 px-2.5 py-0.5 text-xs font-mono text-text-muted">
                    {g.member_count}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Empty groups */}
          {!groupsQuery.isPending &&
            !groupsQuery.isError &&
            groupsQuery.data &&
            groupsQuery.data.length === 0 && (
            <EmptyState>
              <EmptyState.Title>{microcopy.groupsEmpty.title}</EmptyState.Title>
              <EmptyState.Body>{microcopy.groupsEmpty.body}</EmptyState.Body>
            </EmptyState>
          )}
        </div>
      )}
    </div>
  );
}

// Suspense wrapper required because UsersPageInner calls useSearchParams().
// Next 15 statically prerenders client pages; useSearchParams triggers a CSR
// bailout that must be wrapped in Suspense.
export default function UsersPage() {
  return (
    <Suspense fallback={null}>
      <UsersPageInner />
    </Suspense>
  );
}
