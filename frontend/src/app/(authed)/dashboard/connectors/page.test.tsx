/**
 * page.test.tsx — TDD RED-phase tests for the /dashboard/connectors page rewrite.
 *
 * Test 1: Groups connectors under 4 category section headers.
 * Test 2: While loading, SkeletonTable renders.
 * Test 3: A category with zero connectors renders EmptyState with "Add connector" CTA.
 * Test 4: On query error, PartialFailureBanner renders.
 * Test 5: Visiting ?provider=asana pre-opens ConnectorForm in add mode for ASANA.
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// ——— Mock hooks ———
const mockUseConnectorsList = vi.fn();
const mockUseConnectorTypes = vi.fn();
const mockUseUpdateConnector = vi.fn();
const mockUseDeleteConnector = vi.fn();
const mockUseSyncConnector = vi.fn();

vi.mock('@/lib/queries/use-connectors-admin', () => ({
  useConnectorsList: () => mockUseConnectorsList(),
  useConnectorTypes: () => mockUseConnectorTypes(),
  useUpdateConnector: () => mockUseUpdateConnector(),
  useDeleteConnector: () => mockUseDeleteConnector(),
  useSyncConnector: () => mockUseSyncConnector(),
  useCreateConnector: () => ({ mutate: vi.fn(), isPending: false }),
  useTestConnector: () => ({ mutate: vi.fn(), isPending: false, data: null }),
}));

// ——— Mock auth ———
vi.mock('@/lib/auth', () => ({
  useAuth: () => ({ user: { role: 'ADMIN', id: 'u1' }, loading: false }),
}));

// ——— Mock next/navigation ———
const mockSearchParams = new URLSearchParams();
vi.mock('next/navigation', () => ({
  useSearchParams: () => mockSearchParams,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => '/dashboard/connectors',
}));

// ——— Stub state primitives so tests don't need QueryClient for PartialFailureBanner ———
vi.mock('@/components/states', () => ({
  SkeletonTable: ({ className }: { className?: string }) =>
    React.createElement('div', { 'data-testid': 'skeleton-table', className }),
  EmptyState: Object.assign(
    ({ children }: { children: React.ReactNode }) =>
      React.createElement('div', { 'data-testid': 'empty-state' }, children),
    {
      Title: ({ children }: { children: React.ReactNode }) =>
        React.createElement('h2', {}, children),
      Body: ({ children }: { children: React.ReactNode }) =>
        React.createElement('p', {}, children),
      Actions: ({ children }: { children: React.ReactNode }) =>
        React.createElement('div', {}, children),
      Suggestion: ({ children }: { children: React.ReactNode }) =>
        React.createElement('div', { 'data-empty-suggestion': '' }, children),
    },
  ),
  PartialFailureBanner: ({ onRetry }: { onRetry?: () => void }) =>
    React.createElement('div', { 'data-testid': 'partial-failure-banner', onClick: onRetry }),
  PerSourceStatusStrip: () => null,
}));

import ConnectorsPage from './page';

function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: qc }, children);
  };
}

const MOCK_CONNECTOR_TYPES = [
  { type: 'CROWDSTRIKE', name: 'CrowdStrike', description: 'CS connector', fields: ['api_token'], defaults: {}, category: 'vulnerability_scanner', permissions: [], base_urls: {}, setup_url: '' },
  { type: 'NESSUS', name: 'Nessus', description: 'Nessus connector', fields: ['api_token'], defaults: {}, category: 'vulnerability_scanner', permissions: [], base_urls: {}, setup_url: '' },
  { type: 'JIRA', name: 'Jira', description: 'Jira connector', fields: ['api_token'], defaults: {}, category: 'ticketing', permissions: [], base_urls: {}, setup_url: '' },
  { type: 'ASANA', name: 'Asana', description: 'Asana connector', fields: ['api_token'], defaults: {}, category: 'ticketing', permissions: [], base_urls: {}, setup_url: '' },
  { type: 'GOOGLE_WORKSPACE', name: 'Google Workspace', description: 'GW connector', fields: ['service_account_json', 'admin_email'], defaults: {}, category: 'identity_provider', permissions: [], base_urls: {}, setup_url: '' },
  { type: 'JAMF', name: 'Jamf', description: 'Jamf connector', fields: ['api_token'], defaults: {}, category: 'enrichment', permissions: [], base_urls: {}, setup_url: '' },
];

const MOCK_CONNECTORS = [
  {
    id: 'conn-1',
    connector_type: 'CROWDSTRIKE',
    connector_name: 'CrowdStrike Spotlight',
    is_enabled: true,
    config: {},
    has_credentials: true,
    last_sync_at: '2026-06-02T10:00:00Z',
    last_sync_status: 'ok' as const,
    last_sync_record_count: 512,
    sync_interval_minutes: 15,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-06-02T10:00:00Z',
  },
];

const successState = {
  data: MOCK_CONNECTORS,
  isPending: false,
  isLoading: false,
  error: null,
  isSuccess: true,
  refetch: vi.fn(),
};

const typesSuccessState = {
  data: MOCK_CONNECTOR_TYPES,
  isPending: false,
  isLoading: false,
  error: null,
  isSuccess: true,
  refetch: vi.fn(),
};

const loadingState = {
  data: undefined,
  isPending: true,
  isLoading: true,
  error: null,
  isSuccess: false,
  refetch: vi.fn(),
};

const errorState = {
  data: null,
  isPending: false,
  isLoading: false,
  error: new Error('Network error'),
  isSuccess: false,
  refetch: vi.fn(),
};

const mutationStub = { mutate: vi.fn(), isPending: false };

describe('ConnectorsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseConnectorTypes.mockReturnValue(typesSuccessState);
    mockUseUpdateConnector.mockReturnValue(mutationStub);
    mockUseDeleteConnector.mockReturnValue(mutationStub);
    mockUseSyncConnector.mockReturnValue(mutationStub);
  });

  it('Test 1: groups connectors under 4 category section headers', () => {
    mockUseConnectorsList.mockReturnValue(successState);
    render(<ConnectorsPage />, { wrapper: makeWrapper() });

    // The 4 categories should render
    expect(screen.getByText(/vulnerability scanners/i)).toBeTruthy();
    expect(screen.getByText(/ticketing/i)).toBeTruthy();
    expect(screen.getByText(/identity/i)).toBeTruthy();
    expect(screen.getByText(/mdm.*enrichment/i)).toBeTruthy();
  });

  it('Test 2: while loading, SkeletonTable renders', () => {
    mockUseConnectorsList.mockReturnValue(loadingState);
    render(<ConnectorsPage />, { wrapper: makeWrapper() });
    expect(screen.getByTestId('skeleton-table')).toBeTruthy();
  });

  it('Test 3: a category with zero connectors renders EmptyState with Add connector CTA', () => {
    // Only CrowdStrike is configured — ticketing, identity, enrichment categories should be empty
    mockUseConnectorsList.mockReturnValue(successState);
    render(<ConnectorsPage />, { wrapper: makeWrapper() });

    // At least one empty state should be present
    const emptyStates = screen.getAllByTestId('empty-state');
    expect(emptyStates.length).toBeGreaterThanOrEqual(1);

    // "Add connector" CTA text should be present
    const ctaButtons = screen.queryAllByText(/add connector/i);
    expect(ctaButtons.length).toBeGreaterThanOrEqual(1);
  });

  it('Test 4: on query error, PartialFailureBanner renders', () => {
    mockUseConnectorsList.mockReturnValue(errorState);
    render(<ConnectorsPage />, { wrapper: makeWrapper() });
    expect(screen.getByTestId('partial-failure-banner')).toBeTruthy();
  });

  it('Test 5: ?provider=asana pre-opens ConnectorForm in add mode for ASANA', () => {
    mockSearchParams.set('provider', 'asana');
    mockUseConnectorsList.mockReturnValue(successState);
    render(<ConnectorsPage />, { wrapper: makeWrapper() });

    // The form should be open — look for "Save connector" button or the form container
    expect(
      screen.getByRole('button', { name: /save connector/i }) ||
      document.querySelector('[data-connector-form]'),
    ).toBeTruthy();

    // Cleanup
    mockSearchParams.delete('provider');
  });
});
