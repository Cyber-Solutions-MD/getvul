import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

vi.mock('@/lib/api', () => ({ api: vi.fn() }));
import { api } from '@/lib/api';
import { useTicketRules, type TicketRule } from './use-ticket-rules';
import { queryKeys } from './keys';

const apiMock = vi.mocked(api);

function wrap(client: QueryClient) {
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  Wrapper.displayName = 'Wrapper';
  return Wrapper;
}

const MOCK_RULE: TicketRule = {
  id: 'rule-uuid-001',
  name: 'Auto-route criticals',
  is_enabled: true,
  conditions: { severity: ['CRITICAL'], min_risk_score: 80 },
  action: { provider: 'ASANA', project_key: 'proj-1', auto_assign: true, due_days: 7, ticket_mode: 'per_host', max_tickets: 10 },
  saved_filter_id: null,
  schedule_minutes: 1440,
  last_run_at: null,
  last_run_status: null,
  last_run_tickets_created: null,
  created_at: '2026-01-01T00:00:00Z',
};

describe('useTicketRules', () => {
  beforeEach(() => {
    apiMock.mockReset();
  });

  it('hits /api/v1/tickets/rules and is keyed by the stable rules query key', async () => {
    apiMock.mockResolvedValueOnce([MOCK_RULE]);

    const qc = new QueryClient({ defaultOptions: { queries: { retry: 0 } } });
    const { result } = renderHook(() => useTicketRules(), { wrapper: wrap(qc) });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(apiMock).toHaveBeenCalledWith(
      '/api/v1/tickets/rules',
      expect.objectContaining({}),
    );

    // Verify query key matches queryKeys.tickets.rules()
    const queries = qc.getQueryCache().findAll();
    expect(queries[0]?.queryKey).toEqual(queryKeys.tickets.rules());
  });

  it('exposes verbatim backend field names from TicketRule type', async () => {
    apiMock.mockResolvedValueOnce([MOCK_RULE]);

    const qc = new QueryClient({ defaultOptions: { queries: { retry: 0 } } });
    const { result } = renderHook(() => useTicketRules(), { wrapper: wrap(qc) });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const row = result.current.data?.[0];
    // Assert verbatim backend field names from TicketRuleResponse schema
    expect(row?.id).toBe('rule-uuid-001');
    expect(row?.name).toBe('Auto-route criticals');
    expect(row?.is_enabled).toBe(true);
    expect(row?.conditions).toEqual({ severity: ['CRITICAL'], min_risk_score: 80 });
    expect(row?.action).toEqual({ provider: 'ASANA', project_key: 'proj-1', auto_assign: true, due_days: 7, ticket_mode: 'per_host', max_tickets: 10 });
    expect(row?.schedule_minutes).toBe(1440);
    expect(row?.created_at).toBe('2026-01-01T00:00:00Z');
  });
});
