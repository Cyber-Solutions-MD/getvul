/**
 * page.test.tsx — /dashboard/asset-groups management page (32-05-PLAN Task 2).
 *
 * Covers: loading/empty/error states (D-X-01 mandatory), admin CRUD/manage
 * affordances present, non-admin read-only (no create/edit/delete/manage-
 * mutation affordances — the "Manage" READ view itself stays visible).
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

const mockUseAssetGroupsList = vi.fn();
const mockUseDeleteAssetGroup = vi.fn();
const mockUseGroupMembers = vi.fn();
const mockUseAddGroupMember = vi.fn();
const mockUseRemoveGroupMember = vi.fn();
const mockUseGroupExposureOverrides = vi.fn();
const mockUseSetGroupExposureOverride = vi.fn();
const mockUseCreateAssetGroup = vi.fn();
const mockUseUpdateAssetGroup = vi.fn();

vi.mock('@/lib/queries/use-asset-groups', () => ({
  useAssetGroupsList: () => mockUseAssetGroupsList(),
  useDeleteAssetGroup: () => mockUseDeleteAssetGroup(),
  useGroupMembers: () => mockUseGroupMembers(),
  useAddGroupMember: () => mockUseAddGroupMember(),
  useRemoveGroupMember: () => mockUseRemoveGroupMember(),
  useGroupExposureOverrides: () => mockUseGroupExposureOverrides(),
  useSetGroupExposureOverride: () => mockUseSetGroupExposureOverride(),
  useCreateAssetGroup: () => mockUseCreateAssetGroup(),
  useUpdateAssetGroup: () => mockUseUpdateAssetGroup(),
}));

vi.mock('@/lib/queries/use-assets', () => ({
  useAssets: () => ({ data: { items: [] }, isLoading: false, error: null }),
}));

const mockUseAuth = vi.fn();
vi.mock('@/lib/auth', () => ({
  useAuth: () => mockUseAuth(),
}));

import AssetGroupsPage from './page';

function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: qc }, children);
  };
}

const MOCK_GROUPS = [
  {
    id: 'g1',
    tenant_id: 't1',
    name: 'Prod DB tier',
    description: 'Production Postgres hosts',
    member_count: 3,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];

const mutationStub = { mutate: vi.fn(), isPending: false };
const queryEmptyStub = { data: undefined, isLoading: false, error: null, refetch: vi.fn() };

describe('AssetGroupsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseDeleteAssetGroup.mockReturnValue(mutationStub);
    mockUseGroupMembers.mockReturnValue({ data: [], isLoading: false, error: null, refetch: vi.fn() });
    mockUseAddGroupMember.mockReturnValue(mutationStub);
    mockUseRemoveGroupMember.mockReturnValue(mutationStub);
    mockUseGroupExposureOverrides.mockReturnValue({ data: {}, isLoading: false, error: null, refetch: vi.fn() });
    mockUseSetGroupExposureOverride.mockReturnValue(mutationStub);
    mockUseCreateAssetGroup.mockReturnValue(mutationStub);
    mockUseUpdateAssetGroup.mockReturnValue(mutationStub);
  });

  it('renders SkeletonTable while loading', () => {
    mockUseAuth.mockReturnValue({ user: { role: 'ADMIN' } });
    mockUseAssetGroupsList.mockReturnValue({ ...queryEmptyStub, isLoading: true, isPending: true });
    render(<AssetGroupsPage />, { wrapper: makeWrapper() });
    expect(document.querySelector('[data-skeleton-row]')).not.toBeNull();
  });

  it('renders PartialFailureBanner on error', () => {
    mockUseAuth.mockReturnValue({ user: { role: 'ADMIN' } });
    mockUseAssetGroupsList.mockReturnValue({
      ...queryEmptyStub,
      isPending: false,
      error: new Error('Network error'),
    });
    render(<AssetGroupsPage />, { wrapper: makeWrapper() });
    expect(screen.getByText(/retry/i)).toBeInTheDocument();
  });

  it('renders an explained empty state (not a bare "No data") when zero groups, with a New group CTA for admins', () => {
    mockUseAuth.mockReturnValue({ user: { role: 'ADMIN' } });
    mockUseAssetGroupsList.mockReturnValue({ data: [], isPending: false, error: null, refetch: vi.fn() });
    render(<AssetGroupsPage />, { wrapper: makeWrapper() });
    expect(screen.getByText('No asset groups yet')).toBeInTheDocument();
    expect(screen.queryByText(/^No data$/)).toBeNull();
    expect(screen.getAllByText('New group').length).toBeGreaterThanOrEqual(1);
  });

  it('non-admin sees the explained empty state with no New group CTA', () => {
    mockUseAuth.mockReturnValue({ user: { role: 'ANALYST' } });
    mockUseAssetGroupsList.mockReturnValue({ data: [], isPending: false, error: null, refetch: vi.fn() });
    render(<AssetGroupsPage />, { wrapper: makeWrapper() });
    expect(screen.getByText('No asset groups yet')).toBeInTheDocument();
    expect(screen.queryByText('New group')).toBeNull();
    expect(screen.getByText(/Ask an admin/)).toBeInTheDocument();
  });

  it('admin sees name/description/member-count + Manage/Edit/Delete affordances', () => {
    mockUseAuth.mockReturnValue({ user: { role: 'ADMIN' } });
    mockUseAssetGroupsList.mockReturnValue({ data: MOCK_GROUPS, isPending: false, error: null, refetch: vi.fn() });
    render(<AssetGroupsPage />, { wrapper: makeWrapper() });

    expect(screen.getByText('Prod DB tier')).toBeInTheDocument();
    expect(screen.getByText('Production Postgres hosts')).toBeInTheDocument();
    expect(screen.getByTestId('asset-group-member-count-g1')).toHaveTextContent('3');

    expect(screen.getByTestId('manage-group-g1')).toBeInTheDocument();
    expect(screen.getByLabelText('Edit Prod DB tier')).toBeInTheDocument();
    expect(screen.getByLabelText('Delete Prod DB tier')).toBeInTheDocument();
    expect(screen.getByTestId('new-asset-group-btn')).toBeInTheDocument();
  });

  it('non-admin sees Manage but NOT Edit/Delete/New group affordances', () => {
    mockUseAuth.mockReturnValue({ user: { role: 'VIEWER' } });
    mockUseAssetGroupsList.mockReturnValue({ data: MOCK_GROUPS, isPending: false, error: null, refetch: vi.fn() });
    render(<AssetGroupsPage />, { wrapper: makeWrapper() });

    expect(screen.getByTestId('manage-group-g1')).toBeInTheDocument();
    expect(screen.queryByLabelText('Edit Prod DB tier')).toBeNull();
    expect(screen.queryByLabelText('Delete Prod DB tier')).toBeNull();
    expect(screen.queryByTestId('new-asset-group-btn')).toBeNull();
  });
});
