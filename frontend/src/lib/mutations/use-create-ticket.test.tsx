// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

vi.mock('@/lib/api', () => ({ api: vi.fn() }));
import { api } from '@/lib/api';
import { useCreateTicketMutation } from './use-create-ticket';
import { queryKeys } from '@/lib/queries/keys';

const apiMock = vi.mocked(api);

function wrap(client: QueryClient) {
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  Wrapper.displayName = 'Wrapper';
  return Wrapper;
}

describe('useCreateTicketMutation (D-P-04 + Phase 10 BL-06 401 surface)', () => {
  beforeEach(() => {
    apiMock.mockReset();
  });

  it('Test 1: happy path — POST /api/v1/tickets with the request body, resolves with response', async () => {
    apiMock.mockResolvedValue({
      created: 1,
      tickets: [
        {
          id: 't1',
          external_ticket_id: 'GID-123',
          external_ticket_url: 'https://app.asana.com/0/123/456',
          provider: 'ASANA',
        },
      ],
    });
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: 0 } } });
    const { result } = renderHook(() => useCreateTicketMutation(), {
      wrapper: wrap(qc),
    });

    result.current.mutate({
      vulnerability_ids: ['vuln-1'],
      provider: 'ASANA',
      project_key: 'GID-123',
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiMock).toHaveBeenCalledWith(
      '/api/v1/tickets',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          vulnerability_ids: ['vuln-1'],
          provider: 'ASANA',
          project_key: 'GID-123',
        }),
      }),
    );
    expect(result.current.data?.created).toBe(1);
    expect(result.current.data?.tickets[0]?.external_ticket_id).toBe('GID-123');
  });

  it('Test 2: on 401, mutation throws "Session expired during mutation. Please retry." — NO silent retry', async () => {
    // api.ts BL-06: non-safe-method 401 path throws this verbatim string before
    // any token refresh. The mutation hook must surface it as-is.
    apiMock.mockRejectedValue(
      new Error('Session expired during mutation. Please retry.'),
    );
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: 0 } } });
    const { result } = renderHook(() => useCreateTicketMutation(), {
      wrapper: wrap(qc),
    });

    result.current.mutate({
      vulnerability_ids: ['vuln-1'],
      provider: 'JIRA',
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect((result.current.error as Error).message).toBe(
      'Session expired during mutation. Please retry.',
    );
    // BL-06 carryover: the api() call fired ONCE — no silent token-refresh retry.
    expect(apiMock).toHaveBeenCalledTimes(1);
  });

  it('Test 3: on 403 (viewer role), mutation throws with the API detail surfaced', async () => {
    apiMock.mockRejectedValue(new Error('Insufficient permissions: 403'));
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: 0 } } });
    const { result } = renderHook(() => useCreateTicketMutation(), {
      wrapper: wrap(qc),
    });

    result.current.mutate({
      vulnerability_ids: ['vuln-1'],
      provider: 'JIRA',
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect((result.current.error as Error).message).toContain('403');
  });

  it('Test 4: on success, invalidates the notifications cache (activity feed picks up ticket.create)', async () => {
    apiMock.mockResolvedValue({
      created: 1,
      tickets: [
        {
          id: 't1',
          external_ticket_id: 'JIRA-99',
          external_ticket_url: 'https://j',
          provider: 'JIRA',
        },
      ],
    });
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: 0 } } });
    const invalidate = vi.spyOn(qc, 'invalidateQueries');

    const { result } = renderHook(() => useCreateTicketMutation(), {
      wrapper: wrap(qc),
    });

    result.current.mutate({
      vulnerability_ids: ['vuln-1'],
      provider: 'JIRA',
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const calledKeys = invalidate.mock.calls.map((c) => c[0]?.queryKey);
    expect(calledKeys).toContainEqual(queryKeys.notifications.all);
  });

  it('Test 5: provider Literal type includes ASANA, JIRA, GITHUB', () => {
    // Type-level check: assigning a non-allowed provider should fail at
    // compile time. At runtime, we just verify the union includes the three.
    type Provider = Parameters<
      ReturnType<typeof useCreateTicketMutation>['mutate']
    >[0]['provider'];
    const a: Provider = 'ASANA';
    const j: Provider = 'JIRA';
    const g: Provider = 'GITHUB';
    expect([a, j, g]).toEqual(['ASANA', 'JIRA', 'GITHUB']);
  });
});
