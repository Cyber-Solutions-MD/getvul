/**
 * use-exception-mutations.test.ts — tests for useGrantException /
 * useRevokeException (Phase 39 Plan 07).
 *
 * Not explicitly named in 39-07-PLAN.md's `files_modified`, but required to
 * prove the plan's own must_haves ("useGrantException mirrors
 * useStartCampaign, retry:0", "useRevokeException ... invalidates the
 * exceptions list") — mirrors the co-located hook-test convention already
 * established by use-campaign-mutations.test.ts.
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

import { api } from '@/lib/api';
import { useGrantException, useRevokeException } from './use-exception-mutations';
import { queryKeys } from './keys';

const apiMock = vi.mocked(api);

function wrap(qc: QueryClient) {
  const Wrapper = ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: qc }, children);
  Wrapper.displayName = 'Wrapper';
  return Wrapper;
}

describe('useGrantException', () => {
  beforeEach(() => {
    apiMock.mockReset();
    toastFn.mockReset();
  });

  it('POSTs /api/v1/exceptions with the FINDING-scope body and invalidates exceptions.all on success', async () => {
    apiMock.mockResolvedValue({
      id: 'e1',
      type: 'ACCEPTED_RISK',
      scope_type: 'FINDING',
      cve_id: 'CVE-2024-3094',
      vulnerability_id: 'v1',
      asset_id: 'a1',
      asset_group_id: null,
      justification: 'Compensating control',
      approver_user_id: 'u1',
      approver_display_name: 'Ana Sokolova',
      granted_by_user_id: 'u2',
      expires_at: '2027-01-01T00:00:00.000Z',
      revoked_at: null,
      revoked_by_user_id: null,
      resurfaced_audited_at: null,
      created_at: '2026-08-19T00:00:00.000Z',
    });
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: 0 } } });
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries');

    const { result } = renderHook(() => useGrantException(), { wrapper: wrap(qc) });
    result.current.mutate({
      type: 'ACCEPTED_RISK',
      scope_type: 'FINDING',
      vulnerability_id: 'v1',
      justification: 'Compensating control',
      approver_user_id: 'u1',
      expires_at: '2027-01-01T00:00:00.000Z',
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(apiMock).toHaveBeenCalledWith(
      '/api/v1/exceptions',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          type: 'ACCEPTED_RISK',
          scope_type: 'FINDING',
          vulnerability_id: 'v1',
          justification: 'Compensating control',
          approver_user_id: 'u1',
          expires_at: '2027-01-01T00:00:00.000Z',
        }),
      }),
    );
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: queryKeys.exceptions.all });
    expect(toastFn).toHaveBeenCalledWith(
      expect.objectContaining({ variant: 'success', message: 'Exception granted for CVE-2024-3094.' }),
    );
  });

  it('does not close/route on success — that is the caller`s responsibility via a per-call onSuccess', async () => {
    apiMock.mockResolvedValue({ id: 'e1', cve_id: 'CVE-2024-1', type: 'FALSE_POSITIVE', scope_type: 'FINDING' } as never);
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: 0 } } });
    const { result } = renderHook(() => useGrantException(), { wrapper: wrap(qc) });

    const onSuccess = vi.fn();
    result.current.mutate(
      {
        type: 'FALSE_POSITIVE',
        scope_type: 'FINDING',
        vulnerability_id: 'v1',
        justification: 'j',
        approver_user_id: 'u1',
        expires_at: '2027-01-01T00:00:00.000Z',
      },
      { onSuccess },
    );

    await waitFor(() => expect(onSuccess).toHaveBeenCalled());
  });

  it('onError fires a generic toast (the caller separately renders the scoped inline error)', async () => {
    apiMock.mockRejectedValue(new Error('This finding is already remediated — nothing to except.'));
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: 0 } } });
    const { result } = renderHook(() => useGrantException(), { wrapper: wrap(qc) });

    result.current.mutate({
      type: 'ACCEPTED_RISK',
      scope_type: 'FINDING',
      vulnerability_id: 'v1',
      justification: 'j',
      approver_user_id: 'u1',
      expires_at: '2027-01-01T00:00:00.000Z',
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(toastFn).toHaveBeenCalledWith(
      expect.objectContaining({ variant: 'error', message: "Couldn't save the exception — try again." }),
    );
  });
});

describe('useRevokeException', () => {
  beforeEach(() => {
    apiMock.mockReset();
    toastFn.mockReset();
  });

  it('POSTs to /{id}/revoke with no body and invalidates exceptions.all on success (no success toast)', async () => {
    apiMock.mockResolvedValue({ id: 'e1' } as never);
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: 0 } } });
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries');

    const { result } = renderHook(() => useRevokeException('e1'), { wrapper: wrap(qc) });
    result.current.mutate();

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(apiMock).toHaveBeenCalledWith('/api/v1/exceptions/e1/revoke', expect.objectContaining({ method: 'POST' }));
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: queryKeys.exceptions.all });
    expect(toastFn).not.toHaveBeenCalledWith(expect.objectContaining({ variant: 'success' }));
  });

  it('onError fires the exact "Couldn\'t revoke exception" toast', async () => {
    apiMock.mockRejectedValue(new Error('boom'));
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: 0 } } });
    const { result } = renderHook(() => useRevokeException('e1'), { wrapper: wrap(qc) });
    result.current.mutate();

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(toastFn).toHaveBeenCalledWith(
      expect.objectContaining({ variant: 'error', message: "Couldn't revoke exception — try again." }),
    );
  });
});
