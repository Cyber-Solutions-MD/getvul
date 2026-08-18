/**
 * use-campaign-mutations.test.ts — TDD tests for useStartCampaign /
 * useBulkAssign / useCloseCampaign.
 *
 * Not explicitly named in 38-05-PLAN.md's `files_modified`, but required to
 * prove the plan's own <behavior> items for Task 1 ("Start campaign mutation
 * POSTs /api/v1/campaigns; on already_existed=true it routes to
 * /dashboard/campaigns/{id} and fires the D-11 info toast") — mirrors the
 * co-located hook-test convention already established by
 * use-mark-blocked.test.ts / use-campaigns.test.ts.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement, type ReactNode } from 'react';

vi.mock('@/lib/api', () => ({ api: vi.fn() }));

const toastFn = vi.fn();
vi.mock('@/components/ui/ToastProvider', () => ({
  useToast: () => ({ toast: toastFn }),
}));

const pushMock = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: pushMock }),
}));

import { api } from '@/lib/api';
import { useStartCampaign, useBulkAssign, useCloseCampaign } from './use-campaign-mutations';

const apiMock = vi.mocked(api);

function wrap(qc: QueryClient) {
  const Wrapper = ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: qc }, children);
  Wrapper.displayName = 'Wrapper';
  return Wrapper;
}

describe('useStartCampaign', () => {
  beforeEach(() => {
    apiMock.mockReset();
    toastFn.mockReset();
    pushMock.mockClear();
  });

  it('POSTs /api/v1/campaigns with { remediation_id } and routes to the detail page on a fresh create', async () => {
    apiMock.mockResolvedValue({ id: 'c1', remediation_id: 'rem-1', already_existed: false });
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: 0 } } });

    const { result } = renderHook(() => useStartCampaign(), { wrapper: wrap(qc) });
    result.current.mutate('rem-1');

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(apiMock).toHaveBeenCalledWith(
      '/api/v1/campaigns',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ remediation_id: 'rem-1' }),
      }),
    );
    expect(pushMock).toHaveBeenCalledWith('/dashboard/campaigns/c1');
    expect(toastFn).toHaveBeenCalledWith(
      expect.objectContaining({ variant: 'success', message: 'Campaign started for rem-1.' }),
    );
  });

  it('D-11: already_existed=true routes to the SAME detail page and fires the exact redirect toast', async () => {
    apiMock.mockResolvedValue({ id: 'c1', remediation_id: 'rem-1', already_existed: true });
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: 0 } } });

    const { result } = renderHook(() => useStartCampaign(), { wrapper: wrap(qc) });
    result.current.mutate('rem-1');

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(pushMock).toHaveBeenCalledWith('/dashboard/campaigns/c1');
    expect(toastFn).toHaveBeenCalledWith(
      expect.objectContaining({
        variant: 'info',
        message: 'Campaign already running for rem-1 — opening it.',
        duration: 6000,
      }),
    );
  });

  it('onError fires the exact "Couldn\'t start campaign" toast', async () => {
    apiMock.mockRejectedValue(new Error('boom'));
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: 0 } } });

    const { result } = renderHook(() => useStartCampaign(), { wrapper: wrap(qc) });
    result.current.mutate('rem-1');

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(toastFn).toHaveBeenCalledWith(
      expect.objectContaining({ variant: 'error', message: "Couldn't start campaign — try again." }),
    );
    expect(pushMock).not.toHaveBeenCalled();
  });
});

describe('useBulkAssign', () => {
  beforeEach(() => {
    apiMock.mockReset();
    toastFn.mockReset();
  });

  it('POSTs to /{campaignId}/bulk-assign with ONLY the 3 declared fields (T-38-02)', async () => {
    apiMock.mockResolvedValue({
      created_tickets: 2,
      tickets_linked: 5,
      adopted: 1,
      owners: 2,
      failed_owners: [],
    });
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: 0 } } });

    const { result } = renderHook(() => useBulkAssign(), { wrapper: wrap(qc) });
    result.current.mutate({ campaignId: 'c1', provider: 'JIRA', projectKey: 'SEC', dueDays: 14 });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(apiMock).toHaveBeenCalledWith(
      '/api/v1/campaigns/c1/bulk-assign',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ provider: 'JIRA', project_key: 'SEC', due_days: 14 }),
      }),
    );
    expect(toastFn).toHaveBeenCalledWith(
      expect.objectContaining({ variant: 'success', message: '2 tickets created, 1 adopted.' }),
    );
  });
});

describe('useCloseCampaign', () => {
  beforeEach(() => {
    apiMock.mockReset();
    toastFn.mockReset();
  });

  it('POSTs to /{campaignId}/close with no body', async () => {
    apiMock.mockResolvedValue({ status: 'closed' });
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: 0 } } });

    const { result } = renderHook(() => useCloseCampaign(), { wrapper: wrap(qc) });
    result.current.mutate('c1');

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiMock).toHaveBeenCalledWith('/api/v1/campaigns/c1/close', expect.objectContaining({ method: 'POST' }));
  });
});
