/**
 * Tests for UsersExportBar + users page rewrite (Plan 14-04 Task 2 RED).
 *
 * Behaviors:
 *   Test 1: UsersExportBar with selectedIds.length>0 renders ExportButton
 *           (resource="users", label "Export selected"); returns null when none selected.
 *   Test 2: Page renders a Directory/Groups segmented toggle (not horizontal tabs)
 *           bound to ?view; default view=directory.
 *   Test 3: Page renders a ChipBar with status/department/source axes above the
 *           directory table.
 *   Test 4: isPending → SkeletonTable; zero results → EmptyState; query error
 *           → PartialFailureBanner.
 *   Test 5: Switching to view=groups renders the groups list (useTenantGroups)
 *           with an "Export groups" ExportButton.
 *
 * NOTE: UsersExportBar is tested in isolation via its own component test below.
 * The page-level tests use a simplified mock for the export bar.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';

// ─── Mock ExportButton for all tests (avoids localStorage/fetch) ──────────────
vi.mock('@/components/ui/ExportButton', () => ({
  default: ({ resource, label }: { resource: string; label?: string }) => (
    <button data-testid="export-button" data-resource={resource}>
      {label || 'Export CSV'}
    </button>
  ),
}));

// ─── Mock Next.js navigation ──────────────────────────────────────────────────
const mockReplace = vi.fn();
const mockSearchParams = {
  get: vi.fn(),
  getAll: vi.fn(() => []),
  toString: vi.fn(() => ''),
};

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mockReplace }),
  usePathname: () => '/dashboard/users',
  useSearchParams: () => mockSearchParams,
}));

// ─── Mock ChipBar ─────────────────────────────────────────────────────────────
vi.mock('@/components/ui/ChipBar', () => ({
  ChipBar: ({ axes }: { axes: unknown[] }) => (
    <div data-testid="chip-bar" data-axis-count={axes.length} />
  ),
}));

// ─── Mock DirectoryTable ──────────────────────────────────────────────────────
vi.mock('@/components/users/directory-table', () => ({
  DirectoryTable: ({ users }: { users: unknown[] }) => (
    <div data-testid="directory-table" data-user-count={users.length} />
  ),
}));

// ─── Mock state primitives ────────────────────────────────────────────────────
vi.mock('@/components/states', () => ({
  SkeletonTable: () => <div data-testid="skeleton-table" />,
  EmptyState: Object.assign(
    ({ children }: { children: React.ReactNode }) => (
      <div data-testid="empty-state">{children}</div>
    ),
    {
      Title: ({ children }: { children: React.ReactNode }) => <h2>{children}</h2>,
      Body: ({ children }: { children: React.ReactNode }) => <p>{children}</p>,
      Actions: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
      Suggestion: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    }
  ),
  PartialFailureBanner: () => <div data-testid="partial-failure-banner" />,
}));

// ─── Mock hooks ───────────────────────────────────────────────────────────────
import * as directoryUsersModule from '@/lib/queries/use-directory-users';
import * as tenantGroupsModule from '@/lib/queries/use-tenant-groups';

const mockUseDirectoryUsers = vi.spyOn(directoryUsersModule, 'useDirectoryUsers');
const mockUseDirectoryStats = vi.spyOn(directoryUsersModule, 'useDirectoryStats');
const mockUseTenantGroups = vi.spyOn(tenantGroupsModule, 'useTenantGroups');

import UsersPage from './page';

function setupSearchParams(params: Record<string, string | null> = {}) {
  mockSearchParams.get.mockImplementation((key: string) => params[key] ?? null);
  mockSearchParams.getAll.mockReturnValue([]);
}

beforeEach(() => {
  vi.clearAllMocks();
  setupSearchParams({});

  mockUseDirectoryStats.mockReturnValue({
    data: {
      total_users: 5,
      active: 4,
      suspended: 1,
      by_source: { google: 3, okta: 2 },
      departments: [{ name: 'Engineering', count: 3 }],
      has_department: 3,
      has_groups: 2,
      assigned_assets: 4,
      unassigned_assets: 1,
    },
    isPending: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  } as any);

  mockUseTenantGroups.mockReturnValue({
    data: [],
    isPending: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  } as any);
});

// ─── Test 1: UsersExportBar renders null when no selection ────────────────────
// Test the REAL component in isolation (page mock doesn't affect this describe)
// since vi.mock hoisting applies to 'users-export-bar' only for page import.
// We test the export bar's key contracts via the component directly.
describe('UsersExportBar (isolated)', () => {
  // Since vi.mock is hoisted and we can't easily bypass it per-describe,
  // we test via a direct render of the real module.
  // The mock replaces the module export for page-level usage.
  // For isolation tests, we import and verify by rendering the ACTUAL module.

  it('returns null when selectedIds is empty', async () => {
    // Import the real module using the Vitest import.actual override
    const { UsersExportBar: RealUsersExportBar } = await vi.importActual<
      typeof import('@/components/users/users-export-bar')
    >('@/components/users/users-export-bar');

    const { container } = render(
      <RealUsersExportBar selectedIds={[]} onClearSelection={vi.fn()} />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders ExportButton with resource="users" when selectedIds has entries', async () => {
    const { UsersExportBar: RealUsersExportBar } = await vi.importActual<
      typeof import('@/components/users/users-export-bar')
    >('@/components/users/users-export-bar');

    render(
      <RealUsersExportBar selectedIds={['id-1']} onClearSelection={vi.fn()} />
    );
    const btn = screen.getByTestId('export-button');
    expect(btn.getAttribute('data-resource')).toBe('users');
    expect(btn.textContent).toBe('Export selected');
  });
});

// ─── Test 2: Directory/Groups segmented toggle ────────────────────────────────
describe('UsersPage — Directory/Groups toggle', () => {
  it('renders a Directory/Groups segmented toggle when directory view active', () => {
    mockUseDirectoryUsers.mockReturnValue({
      data: { items: [], total: 0, page: 1, page_size: 25, pages: 0 },
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any);

    render(<UsersPage />);
    const directoryBtn = screen.getByRole('button', { name: /directory/i });
    const groupsBtn = screen.getByRole('button', { name: /groups/i });
    expect(directoryBtn).toBeTruthy();
    expect(groupsBtn).toBeTruthy();
  });

  it('does NOT use horizontal tab pattern (no border-b-2 or border-indigo classes)', () => {
    mockUseDirectoryUsers.mockReturnValue({
      data: { items: [], total: 0, page: 1, page_size: 25, pages: 0 },
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any);

    const { container } = render(<UsersPage />);
    expect(container.innerHTML).not.toMatch(/border-b-2/);
    expect(container.innerHTML).not.toMatch(/border-indigo/);
  });
});

// ─── Test 3: ChipBar with status/department/source axes ──────────────────────
describe('UsersPage — ChipBar', () => {
  it('renders a ChipBar in directory view', () => {
    mockUseDirectoryUsers.mockReturnValue({
      data: { items: [], total: 0, page: 1, page_size: 25, pages: 0 },
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any);

    render(<UsersPage />);
    expect(screen.getByTestId('chip-bar')).toBeTruthy();
  });

  it('passes at least 3 axes (status/department/source) to ChipBar', () => {
    mockUseDirectoryUsers.mockReturnValue({
      data: { items: [], total: 0, page: 1, page_size: 25, pages: 0 },
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any);

    render(<UsersPage />);
    const chipBar = screen.getByTestId('chip-bar');
    expect(Number(chipBar.getAttribute('data-axis-count'))).toBeGreaterThanOrEqual(3);
  });
});

// ─── Test 4: State patterns ───────────────────────────────────────────────────
describe('UsersPage — state patterns', () => {
  it('renders SkeletonTable when isPending', () => {
    mockUseDirectoryUsers.mockReturnValue({
      data: undefined,
      isPending: true,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any);

    render(<UsersPage />);
    expect(screen.getByTestId('skeleton-table')).toBeTruthy();
  });

  it('renders EmptyState when items is empty and not pending', () => {
    mockUseDirectoryUsers.mockReturnValue({
      data: { items: [], total: 0, page: 1, page_size: 25, pages: 0 },
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any);

    render(<UsersPage />);
    expect(screen.getByTestId('empty-state')).toBeTruthy();
  });

  it('renders PartialFailureBanner when query errors', () => {
    mockUseDirectoryUsers.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      error: new Error('Network error'),
      refetch: vi.fn(),
    } as any);

    render(<UsersPage />);
    expect(screen.getByTestId('partial-failure-banner')).toBeTruthy();
  });
});

// ─── Test 5: Groups view ──────────────────────────────────────────────────────
describe('UsersPage — groups view', () => {
  it('renders groups export button when in groups view', () => {
    setupSearchParams({ view: 'groups' });

    mockUseTenantGroups.mockReturnValue({
      data: [{ name: 'Engineering', member_count: 5, members: [] }],
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any);

    render(<UsersPage />);
    const groupsExportBtns = screen.getAllByTestId('export-button');
    expect(groupsExportBtns.some(btn => btn.getAttribute('data-resource') === 'groups')).toBe(true);
  });

  it('renders group names in groups view', () => {
    setupSearchParams({ view: 'groups' });

    mockUseTenantGroups.mockReturnValue({
      data: [{ name: 'Engineering', member_count: 5, members: [] }],
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any);

    render(<UsersPage />);
    expect(screen.getByText('Engineering')).toBeTruthy();
  });
});
